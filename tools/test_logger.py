"""Runs the in-game logger in real Lua 5.1 against a mocked Civ 5 API.

Catches what the game would only report at load time: a UTF-8 BOM, syntax
errors, runtime errors and missing fields. Needs: pip install -r requirements-dev.txt

    python tools/test_logger.py
"""
import os
import sys
try:
    from lupa import lua51 as lupa_mod
except ImportError:
    import lupa as lupa_mod
L = lupa_mod.LuaRuntime(unpack_returned_tuples=True)

LUA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game", "UI", "CivStatsLogger.lua")
raw = open(LUA, "rb").read()
assert not raw.startswith(b"\xef\xbb\xbf"), "CivStatsLogger.lua starts with a UTF-8 BOM: the game cannot load it"
src = raw.decode("utf-8")
mock = r'''
OUT = {}
function print(s) OUT[#OUT+1] = tostring(s) end
local handlers = {}
local function event() local e = {} function e.Add(f) handlers[#handlers+1] = f end return e end
Events = { ActivePlayerTurnStart = event(), LoadScreenClose = event() }
GameDefines = { MAX_MAJOR_CIVS = 3 }
YieldTypes = { YIELD_PRODUCTION = 1 }
Locale = { ConvertTextKey = function(k) return k end }
local function rows(list)  -- GameInfo tables: callable iterator + index by id
  local t = {}
  for i, r in ipairs(list) do t[r.ID] = r end
  return setmetatable(t, { __call = function() local i = 0 return function() i = i + 1 return list[i] end end })
end
GameInfo = {
  Civilizations = rows({ {ID=0, Type="CIVILIZATION_ROME", ShortDescription="Rome"}, {ID=1, Type="CIVILIZATION_GREECE", ShortDescription="Greece"}, {ID=2, Type="CIVILIZATION_CELTS", ShortDescription="Celts"} }),
  Technologies = rows({ {ID=0}, {ID=1}, {ID=2} }),
  Policies = rows({ {ID=0}, {ID=1} }),
  PolicyBranchTypes = rows({ {ID=0}, {ID=1} }),
  GameSpeeds = rows({ {ID=0, Type="GAMESPEED_STANDARD", GrowthPercent=100} }),
  Worlds = rows({ {ID=0, Type="WORLDSIZE_STANDARD", DefaultPlayers=8} }),
}
Game = { GetGameTurn=function() return 7 end, GetActivePlayer=function() return 0 end, GetActiveTeam=function() return 0 end, GetGameSpeedType=function() return 0 end }
Map = { GetWorldSize=function() return 0 end, GetGridSize=function() return 80, 52 end, PlotDistance=function(a,b,c,d) return math.abs(a-c)+math.abs(b-d) end }
local function plot(x, y) return { GetX=function() return x end, GetY=function() return y end, IsRevealed=function(self, team, dbg) return true end } end
local function city(x, y) return { Plot=function() return plot(x, y) end, GetX=function() return x end, GetY=function() return y end,
  GetYieldRate=function(self, yt) return 5 end, FoodDifference=function() return 2 end } end
local function player(id, cities)
  local p = { id = id }
  setmetatable(p, { __index = function(t, k) return function() return 3 end end })  -- any getter -> 3
  p.IsEverAlive = function() return true end
  p.IsAlive = function() return true end
  p.GetTeam = function() return id end
  p.GetCivilizationType = function() return id end
  p.Cities = function() local i = 0 return function() i = i + 1 return cities[i] end end
  p.GetStartingPlot = function() return plot(10 + id, 20) end
  p.HasPolicy = function(self, pid) return pid == 0 end
  p.IsPolicyBranchUnlocked = function(self, b) return b == 0 end
  return p
end
Players = { [0] = player(0, { city(10, 20) }), [1] = player(1, { city(14, 22) }), [2] = player(2, { city(40, 40) }) }
local function team(id) return { IsHasMet=function() return true end, IsAtWar=function(self, o) return o == 2 end,
  IsHasTech=function(self, t) return t < 2 end, GetTeamTechs=function() return { GetNumTechsKnown=function() return 2 end } end } end
Teams = { [0] = team(0), [1] = team(1), [2] = team(2) }
function FIRE() for _, f in ipairs(handlers) do f() end end
'''
L.execute(mock)
f = L.eval("loadstring")(src)
if f is None or isinstance(f, tuple) and f[0] is None:
    print("COMPILE ERROR:", f); sys.exit(1)
(f[0] if isinstance(f, tuple) else f)()
L.execute("FIRE()")
out = list(L.globals().OUT.values())
text = "\n".join(out)
for need in ("CIVSTATS_START|7|v=3", "loggerVersion=3", "gameId=ROME-10-20-80x52", "techIds=0,1",
             "dist=6", "war=1", "speed=GAMESPEED_STANDARD"):
    assert need in text, f"missing in logger output: {need}"
assert "CIVSTATS_ERROR" not in text, text
print(f"OK: {len(out)} lines, logger runs in {L.eval('_VERSION')} against the mocked game API")
