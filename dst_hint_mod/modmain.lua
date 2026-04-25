-- DST Hint System - State Exporter
-- Collects player & world metadata and exports it for the hint recommendation system.

local DST = GLOBAL.TheSim:GetGameID() == "DST"
if not DST then return end
if GLOBAL.TheNet:IsDedicated() then return end

-- ── Import missing sandbox globals ────────────────────────────────────────────
-- DST mod env includes: pairs, ipairs, math, table, string, type, tostring, print
-- but NOT: pcall, xpcall, error, tonumber, rawget, unpack
local pcall    = GLOBAL.pcall
local tonumber = GLOBAL.tonumber

-- ── Config ────────────────────────────────────────────────────────────────────
local EXPORT_INTERVAL   = GetModConfigData("EXPORT_INTERVAL") or 10
local NEARBY_RADIUS     = GetModConfigData("NEARBY_RADIUS")   or 15
local SHOW_NOTIFICATION = GetModConfigData("SHOW_NOTIFICATION")
local HOTKEY_CHAR       = GetModConfigData("HOTKEY") or "H"

-- ── Tile → Biome mapping (guarded: GROUND constants may not all exist) ────────
local TILE_BIOME = {}
do
    local G = GLOBAL.GROUND
    local function reg(key, name)
        if G and G[key] ~= nil then TILE_BIOME[G[key]] = name end
    end
    reg("GRASS",          "grassland")
    reg("FOREST",         "forest")
    reg("ROCKY",          "rocky")
    reg("DIRT",           "desert")
    reg("SAVANNA",        "savanna")
    reg("MARSH",          "swamp")
    reg("WOODFLOOR",      "wooden_floor")
    reg("CAVE",           "cave")
    reg("FUNGUS",         "fungal_forest")
    reg("FUNGUS_MOON",    "moon_fungal")
    reg("SINKHOLE",       "sinkhole")
    reg("UNDERROCK",      "cave_underrock")
    reg("MUD",            "muddy")
    reg("BRICK",          "ruins")
    reg("BRICK_GLOW",     "ruins_ancient")
    reg("CHECKER",        "ruins_checker")
    reg("PEBBLEBEACH",    "pebble_beach")
    reg("OCEAN_COASTAL",  "ocean_coastal")
    reg("OCEAN_DEEP",     "ocean_deep")
    reg("OCEAN_SWELL",    "ocean_swell")
    reg("OCEAN_BRINEPOOL","brinepool")
end

-- ── Boss prefabs to track kills ───────────────────────────────────────────────
local BOSS_PREFABS = {
    "deerclops", "bearger", "moose", "dragonfly",
    "antlion", "toadstool", "toadstool_dark",
    "klaus", "crabking", "malbatross",
    "beequeen", "spiderqueen",
    "ancient_guardian", "eyeofterror",
}
local boss_kills = {}

-- Key recipes to track (instead of dumping all hundreds of recipes)
local KEY_RECIPES = {
    "axe", "pickaxe", "hammer", "shovel",
    "torch", "campfire", "firepit",
    "backpack", "piggyback",
    "logsuit", "footballhat", "spear",
    "sciencemachine", "alchemyengine",
    "prestihatitator", "shadowmanipulator",
    "icebox", "crockpot", "dryer",
    "boat_kit", "boat_lantern",
}

-- FindEntities cant_tags: skip FX, invisible, and limbo entities
local FIND_CANT_TAGS = {"FX", "INLIMBO", "NOCLICK", "shadow", "playerghost"}
local MAX_NEARBY     = 25

-- ── Helpers ───────────────────────────────────────────────────────────────────

local function safe_floor(v)
    return v and math.floor(v) or 0
end

local function get_biome(player)
    local x, y, z = player.Transform:GetWorldPosition()
    local tile = GLOBAL.TheWorld.Map:GetTileAtPoint(x, y, z)
    if GLOBAL.TheWorld:HasTag("cave") then
        return TILE_BIOME[tile] or "cave"
    end
    return TILE_BIOME[tile] or "unknown"
end

local function get_vitals(player)
    local hp  = player.components.health
    local hun = player.components.hunger
    local san = player.components.sanity
    local tmp = player.components.temperature
    local wet = player.components.moisture
    return {
        health  = {
            current = safe_floor(hp  and hp.currenthealth),
            max     = safe_floor(hp  and hp.maxhealth),
            percent = hp and math.floor(hp:GetPercent() * 100) or 0,
        },
        hunger  = {
            current = safe_floor(hun and hun.current),
            max     = safe_floor(hun and hun.max),
            percent = hun and math.floor(hun:GetPercent() * 100) or 0,
        },
        sanity  = {
            current = safe_floor(san and san.current),
            max     = safe_floor(san and san.max),
            percent = san and math.floor(san:GetPercent() * 100) or 0,
        },
        temperature    = safe_floor(tmp and tmp.current),
        wetness        = safe_floor(wet and wet.moisture),
        is_freezing    = (tmp ~= nil) and tmp:IsFreezing()    or false,
        is_overheating = (tmp ~= nil) and tmp:IsOverheating() or false,
    }
end

local function get_inventory(player)
    local inv = player.components.inventory
    if not inv then return { items = {}, equipped = {} } end

    local items = {}
    for slot = 1, inv.maxslots do
        local item = inv:GetItemInSlot(slot)
        if item then
            table.insert(items, {
                prefab = item.prefab,
                slot   = slot,
                stack  = item.components.stackable
                         and item.components.stackable:StackSize() or 1,
                dur    = item.components.finiteuses
                         and math.floor(item.components.finiteuses:GetPercent() * 100) or nil,
            })
        end
    end

    -- Backpack contents
    local backpack = inv:GetEquippedItem(GLOBAL.EQUIPSLOTS.BACK)
    if backpack and backpack.components.container then
        local numslots = backpack.components.container.numslots or 0
        for slot = 1, numslots do
            local item = backpack.components.container:GetItemInSlot(slot)
            if item then
                table.insert(items, {
                    prefab = item.prefab,
                    slot   = "bp_" .. slot,
                    stack  = item.components.stackable
                             and item.components.stackable:StackSize() or 1,
                })
            end
        end
    end

    local equipped = {}
    for _, eslot in pairs(GLOBAL.EQUIPSLOTS) do
        local item = inv:GetEquippedItem(eslot)
        if item then
            equipped[tostring(eslot)] = {
                prefab = item.prefab,
                dur    = item.components.finiteuses
                         and math.floor(item.components.finiteuses:GetPercent() * 100) or nil,
            }
        end
    end

    return { items = items, equipped = equipped }
end

local function get_tech_level(player)
    local builder = player.components.builder
    if not builder or not builder.accessible_tech_trees then return "primitive" end
    local trees = builder.accessible_tech_trees
    local sci  = trees["SCIENCE"] or 0
    local mag  = trees["MAGIC"]   or 0
    if mag >= 2 then return "magic_advanced"
    elseif mag >= 1 then return "magic_basic"
    elseif sci >= 2 then return "science_advanced"
    elseif sci >= 1 then return "science_basic"
    end
    return "primitive"
end

local function get_known_recipes(player)
    local builder = player.components.builder
    if not builder or not builder.recipes then return {} end
    local known = {}
    for _, recipe in ipairs(KEY_RECIPES) do
        -- builder.recipes[name] is true if the player has permanently learned it
        if builder.recipes[recipe] then
            table.insert(known, recipe)
        end
    end
    return known
end

local function get_nearby(player)
    local x, y, z = player.Transform:GetWorldPosition()
    -- CRITICAL: pass cant_tags to avoid returning FX/particles/invisible entities
    local ents = GLOBAL.TheSim:FindEntities(x, y, z, NEARBY_RADIUS, nil, FIND_CANT_TAGS)
    local result = {}
    local seen   = {}
    local count  = 0

    for _, ent in ipairs(ents) do
        if count >= MAX_NEARBY then break end
        if ent ~= player and ent.prefab and not seen[ent.prefab] then
            seen[ent.prefab] = true
            count = count + 1
            table.insert(result, {
                prefab       = ent.prefab,
                is_enemy     = ent:HasTag("monster") or ent:HasTag("hostile"),
                is_boss      = ent:HasTag("epic"),
                is_resource  = ent:HasTag("pickable") or ent:HasTag("choppable")
                               or ent:HasTag("mine") or ent:HasTag("dig"),
                is_structure = ent:HasTag("structure"),
            })
        end
    end
    return result
end

local function get_world_state()
    local ws = GLOBAL.TheWorld.state
    return {
        season          = ws.season or "unknown",
        day             = (ws.cycles or 0) + 1,
        day_in_season   = ws.elapseddaysinseason or 0,
        days_remaining  = ws.remainingdaysinseason or 0,
        time_of_day     = ws.isday and "day" or ws.isdusk and "dusk" or "night",
        world_temp      = safe_floor(ws.temperature),
        is_full_moon    = ws.fullmoon    or false,
        is_raining      = ws.israining  or false,
        is_snowing      = ws.issnowing  or false,
        is_cave         = GLOBAL.TheWorld:HasTag("cave"),
    }
end

-- ── JSON encoder ──────────────────────────────────────────────────────────────

local function json_encode(t, depth)
    depth = depth or 0
    if depth > 5 then return '"..."' end
    local typ = type(t)
    if typ == "nil"     then return "null"
    elseif typ == "boolean" then return tostring(t)
    elseif typ == "number" then
        if t ~= t or t == math.huge or t == -math.huge then return "null" end
        return tostring(math.floor(t) == t and math.floor(t) or t)
    elseif typ == "string" then
        return '"' .. t:gsub('\\','\\\\'):gsub('"','\\"'):gsub('\n','\\n'):gsub('\r','') .. '"'
    elseif typ == "table" then
        local is_arr = (#t > 0)
        local parts  = {}
        if is_arr then
            for i, v in ipairs(t) do
                parts[i] = json_encode(v, depth + 1)
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            for k, v in pairs(t) do
                if type(k) == "string" then
                    table.insert(parts,
                        '"' .. k .. '":' .. json_encode(v, depth + 1))
                end
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    end
    return "null"
end

-- ── Main export ───────────────────────────────────────────────────────────────

local function export_state(manual)
    local player = GLOBAL.ThePlayer
    if not player then return end

    local ok, result = pcall(function()
        local inv = get_inventory(player)
        return {
            character     = player.prefab,
            world         = get_world_state(),
            biome         = get_biome(player),
            vitals        = get_vitals(player),
            inventory     = inv,
            tech_level    = get_tech_level(player),
            known_recipes = get_known_recipes(player),
            nearby        = get_nearby(player),
            flags = {
                has_backpack   = inv.equipped["back"] ~= nil,
                has_armor      = inv.equipped["body"] ~= nil,
                has_helmet     = inv.equipped["head"] ~= nil,
                has_weapon     = inv.equipped["hands"] ~= nil,
                boss_kills     = boss_kills,
            },
        }
    end)

    if not ok then
        print("[HINT_SYSTEM_ERROR] " .. tostring(result))
        return
    end

    local ok2, json_str = pcall(json_encode, result)
    if not ok2 then
        print("[HINT_SYSTEM_ERROR] JSON encode failed")
        return
    end

    GLOBAL.TheSim:SetPersistentString("dst_hint_system_state", json_str, false, nil)
    print("[HINT_SYSTEM_STATE]" .. json_str)

    if manual and SHOW_NOTIFICATION then
        local talker = player.components.talker
        if talker then
            talker:Say("Hint system: state exported.", 2, true)
        end
    end
end

-- ── Boss kill tracking ────────────────────────────────────────────────────────

for _, boss in ipairs(BOSS_PREFABS) do
    AddPrefabPostInit(boss, function(inst)
        inst:ListenForEvent("death", function(victim)
            if victim and victim.prefab and not boss_kills[victim.prefab] then
                boss_kills[victim.prefab] = (GLOBAL.TheWorld.state.cycles or 0) + 1
                print("[HINT_SYSTEM_BOSS] " .. victim.prefab .. " killed")
            end
        end)
    end)
end

-- ── World-dependent setup (AddPrefabPostInit fires when world actually loads) ──
-- AddGamePostInit fires at main menu load where TheWorld is nil — do NOT use
-- TheWorld or ThePlayer inside AddGamePostInit.

AddPrefabPostInit("world", function(inst)
    -- inst == TheWorld at this point

    -- Periodic timer
    inst:DoPeriodicTask(EXPORT_INTERVAL, function()
        export_state(false)
    end)

    -- Day change trigger
    inst:ListenForEvent("ms_newday", function()
        export_state(false)
    end)

    -- Season change trigger
    inst:ListenForEvent("seasonchange", function()
        export_state(false)
    end)

    -- Initial export: delay 3s so the local player has time to spawn
    inst:DoTaskInTime(3, function()
        export_state(false)
    end)

    print("[HINT_SYSTEM] World loaded. Interval=" .. EXPORT_INTERVAL
          .. "s  Radius=" .. NEARBY_RADIUS)
end)

-- ── Keyboard handler (TheInput exists at GamePostInit, TheWorld not needed) ───

AddGamePostInit(function()
    if HOTKEY_CHAR and HOTKEY_CHAR ~= "" then
        local KEY = GLOBAL["KEY_" .. HOTKEY_CHAR]
        if KEY then
            GLOBAL.TheInput:AddKeyUpHandler(KEY, function()
                local p = GLOBAL.ThePlayer
                if p and p.HUD and not p.HUD:HasInputFocus() then
                    export_state(true)
                end
            end)
        end
    end
end)
