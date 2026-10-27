-- CivStatsLogger: writes per-turn stats of every major civ to Lua.log.
-- Only reads game state, so it never causes multiplayer desyncs.
-- Line format: CIVSTATS|turn|playerId|isMe|met|civName|key=value;key=value;...

-- Bump when the logged fields change; the viewer warns about older loggers.
LOGGER_VERSION = 3

local function safe(f, ...)
	local ok, v = pcall(f, ...)
	if ok and type(v) == "number" then return v end
	return 0
end

local EXTRA_GETTERS = {
	-- score breakdown
	"GetScoreFromCities", "GetScoreFromPopulation", "GetScoreFromLand", "GetScoreFromWonders",
	"GetScoreFromTechs", "GetScoreFromFutureTech", "GetScoreFromPolicies",
	"GetScoreFromGreatWorks", "GetScoreFromReligion",
	-- gold
	"CalculateGrossGold", "CalculateInflatedCosts", "CalculateUnitCost", "CalculateUnitSupply",
	"GetBuildingGoldMaintenance", "GetImprovementGoldMaintenance",
	"GetGoldFromCitiesTimes100", "GetGoldPerTurnFromTradeRoutesTimes100",
	"GetCityConnectionGoldTimes100", "GetGoldPerTurnFromDiplomacy", "GetGoldPerTurnFromReligion",
	"GetGoldPerTurnFromTraits", "GetLifetimeGrossGold",
	-- science
	"GetScienceFromCitiesTimes100", "GetScienceFromOtherPlayersTimes100",
	"GetScienceFromHappinessTimes100", "GetScienceFromResearchAgreementsTimes100",
	"GetScienceFromBudgetDeficitTimes100", "GetResearchTurnsLeft", "GetCurrentEra",
	-- culture / tourism / great works
	"GetJONSCulture", "GetJONSCultureEverGenerated", "GetJONSCulturePerTurnFromCities",
	"GetJONSCulturePerTurnFromExcessHappiness", "GetJONSCulturePerTurnFromMinorCivs",
	"GetCulturePerTurnFromReligion", "GetNextPolicyCost", "GetNumPolicyBranchesFinished",
	"GetNumGreatWorks", "GetNumGreatWorkSlots", "GetNumWorldWonders",
	-- faith
	"GetFaith", "GetFaithPerTurnFromCities", "GetFaithPerTurnFromReligion",
	"GetFaithPerTurnFromMinorCivs", "GetMinimumFaithNextGreatProphet",
	-- happiness
	"GetHappiness", "GetUnhappiness", "GetHappinessFromLuxury", "GetHappinessFromBuildings",
	"GetHappinessFromPolicies", "GetHappinessFromReligion", "GetHappinessFromMinorCivs",
	"GetHappinessFromNaturalWonders", "GetHappinessFromTradeRoutes",
	"GetUnhappinessFromCityCount", "GetUnhappinessFromCityPopulation",
	"GetUnhappinessFromOccupiedCities", "GetUnhappinessFromPublicOpinion",
	"GetGoldenAgeTurns", "GetGoldenAgeProgressMeter", "GetGoldenAgeProgressThreshold",
	-- military
	"GetNumUnitsSupplied", "GetNumUnitsOutOfSupply", "GetLifetimeCombatExperience",
	"GetNavalCombatExperience", "GetWarmongerThreat",
	-- trade / diplomacy / espionage
	"GetNumInternationalTradeRoutesUsed", "GetNumInternationalTradeRoutesAvailable",
	"GetNumCivsInfluentialOn", "GetNumCivsToBeInfluentialOn",
	-- great people
	"GetGreatPeopleRateModifier", "GetNumFreeGreatPeople",
}

local function collect(p, pTeam)
	local s = {}
	s.score      = safe(p.GetScore, p)
	s.gold       = safe(p.GetGold, p)
	s.goldRate   = safe(p.CalculateGoldRate, p)
	s.science    = safe(p.GetScience, p)
	s.culture    = safe(p.GetTotalJONSCulturePerTurn, p)
	s.faith      = safe(p.GetTotalFaithPerTurn, p)
	s.tourism    = safe(p.GetTourism, p)
	s.military   = safe(p.GetMilitaryMight, p)
	s.population = safe(p.GetTotalPopulation, p)
	s.cities     = safe(p.GetNumCities, p)
	s.happiness  = safe(p.GetExcessHappiness, p)
	s.policies   = safe(p.GetNumPolicies, p)
	s.land       = safe(p.GetTotalLand, p)
	s.techs      = safe(function() return pTeam:GetTeamTechs():GetNumTechsKnown() end)
	s.units      = safe(p.GetNumUnits, p)

	-- Every other argument-free numeric getter, logged under its own name.
	-- Missing methods just log 0, so this list is safe across game versions.
	for _, name in ipairs(EXTRA_GETTERS) do
		local v = safe(function() return p[name](p) end)
		if name:find("Times100$") then
			name = name:gsub("Times100$", "")
			v = v / 100
		end
		s[name] = v
	end

	-- City totals
	local prod, food, starving, wonders = 0, 0, 0, 0
	for city in p:Cities() do
		prod = prod + safe(function() return city:GetYieldRate(YieldTypes.YIELD_PRODUCTION) end)
		local fd = safe(function() return city:FoodDifference() end)
		food = food + fd
		if fd < 0 then starving = starving + 1 end
	end
	s.production = prod
	s.foodSurplus = food
	s.starvingCities = starving
	return s
end

-- Relation of a rival to the active player. Distance only counts rival cities
-- the active player has already revealed on the map, so nothing hidden leaks.
--   dist = tiles between your nearest city and their nearest known city (-1 = none known)
--   war  = 1 if at war with you
local function relation(pMe, myTeam, p, team)
	local r = { dist = -1, war = 0, knownCities = 0 }
	r.war = safe(function() return myTeam:IsAtWar(team) and 1 or 0 end)
	local myTeamId = pMe:GetTeam()
	local best = -1
	for c in p:Cities() do
		local plot = c:Plot()
		if plot and plot:IsRevealed(myTeamId, false) then
			r.knownCities = r.knownCities + 1
			for mc in pMe:Cities() do
				local d = Map.PlotDistance(mc:GetX(), mc:GetY(), c:GetX(), c:GetY())
				if best < 0 or d < best then best = d end
			end
		end
	end
	r.dist = best
	return r
end

-- Your own research and social policies (only for the active player), as
-- comma-separated database IDs so the viewer can suggest what to take next.
local function progress(p, pTeam)
	local techs, policies, branches = {}, {}, {}
	for t in GameInfo.Technologies() do
		if pTeam:IsHasTech(t.ID) then techs[#techs + 1] = t.ID end
	end
	for pol in GameInfo.Policies() do
		if p:HasPolicy(pol.ID) then policies[#policies + 1] = pol.ID end
	end
	for b in GameInfo.PolicyBranchTypes() do
		if p:IsPolicyBranchUnlocked(b.ID) then branches[#branches + 1] = b.ID end
	end
	return {
		techIds = table.concat(techs, ","),
		policyIds = table.concat(policies, ","),
		branchIds = table.concat(branches, ","),
		research = safe(p.GetCurrentResearch, p),
		culturePoints = safe(p.GetJONSCulture, p),
	}
end

-- Game settings the viewer needs to scale its benchmarks, plus a game id that
-- stays the same when the game is saved and loaded again (your civ, your
-- starting tile and the map size), so one game across sessions is one record.
local function gameInfo(p)
	local info = { loggerVersion = LOGGER_VERSION }
	local speed = GameInfo.GameSpeeds[Game.GetGameSpeedType()]
	info.speed = speed and speed.Type or "?"
	info.speedPercent = speed and speed.GrowthPercent or 100
	local world = GameInfo.Worlds[Map.GetWorldSize()]
	info.worldSize = world and world.Type or "?"
	info.worldPlayers = world and world.DefaultPlayers or 8
	local w, h = Map.GetGridSize()
	info.mapW, info.mapH = w or 0, h or 0
	local start = p:GetStartingPlot()
	local civ = GameInfo.Civilizations[p:GetCivilizationType()]
	info.gameId = string.format("%s-%d-%d-%dx%d", civ and civ.Type:gsub("CIVILIZATION_", "") or "X",
		start and start:GetX() or -1, start and start:GetY() or -1, info.mapW, info.mapH)
	return info
end

local function LogTurn()
	local turn = Game.GetGameTurn()
	local me = Game.GetActivePlayer()
	local myTeam = Teams[Game.GetActiveTeam()]
	print("CIVSTATS_TURN|" .. turn .. "|v=" .. LOGGER_VERSION)
	for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
		local p = Players[i]
		-- one civ failing must not stop the others: report and go on
		local ok, err = pcall(LogPlayer, turn, i, p, me, myTeam)
		if not ok then
			print("CIVSTATS_ERROR|" .. turn .. "|" .. i .. "|" .. tostring(err))
		end
	end
end

function LogPlayer(turn, i, p, me, myTeam)
		if p and p:IsEverAlive() and p:IsAlive() then
			local team = p:GetTeam()
			local met = (i == me) or myTeam:IsHasMet(team)
			local name = Locale.ConvertTextKey(GameInfo.Civilizations[p:GetCivilizationType()].ShortDescription)
			local parts = {}
			local s = collect(p, Teams[team])
			if i ~= me then
				for k, v in pairs(relation(Players[me], myTeam, p, team)) do s[k] = v end
			else
				for k, v in pairs(progress(p, Teams[team])) do s[k] = v end
				for k, v in pairs(gameInfo(p)) do s[k] = v end
			end
			for k, v in pairs(s) do
				parts[#parts + 1] = k .. "=" .. tostring(v)
			end
			print(string.format("CIVSTATS|%d|%d|%d|%d|%s|%s",
				turn, i, (i == me) and 1 or 0, met and 1 or 0, name, table.concat(parts, ";")))
		end
end

Events.ActivePlayerTurnStart.Add(LogTurn)
Events.LoadScreenClose.Add(function()
	print("CIVSTATS_START|" .. Game.GetGameTurn() .. "|v=" .. LOGGER_VERSION)
	LogTurn()
end)
