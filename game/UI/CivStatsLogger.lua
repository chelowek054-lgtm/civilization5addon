-- CivStatsLogger: writes per-turn stats of every major civ to Lua.log.
-- Only reads game state, so it never causes multiplayer desyncs.
-- Line format: CIVSTATS|turn|playerId|isMe|met|civName|key=value;key=value;...

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

local function LogTurn()
	local turn = Game.GetGameTurn()
	local me = Game.GetActivePlayer()
	local myTeam = Teams[Game.GetActiveTeam()]
	print("CIVSTATS_TURN|" .. turn)
	for i = 0, GameDefines.MAX_MAJOR_CIVS - 1 do
		local p = Players[i]
		if p and p:IsEverAlive() and p:IsAlive() then
			local team = p:GetTeam()
			local met = (i == me) or myTeam:IsHasMet(team)
			local name = Locale.ConvertTextKey(GameInfo.Civilizations[p:GetCivilizationType()].ShortDescription)
			local parts = {}
			for k, v in pairs(collect(p, Teams[team])) do
				parts[#parts + 1] = k .. "=" .. tostring(v)
			end
			print(string.format("CIVSTATS|%d|%d|%d|%d|%s|%s",
				turn, i, (i == me) and 1 or 0, met and 1 or 0, name, table.concat(parts, ";")))
		end
	end
end

Events.ActivePlayerTurnStart.Add(LogTurn)
Events.LoadScreenClose.Add(function()
	print("CIVSTATS_START|" .. Game.GetGameTurn())
	LogTurn()
end)
