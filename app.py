import streamlit as st
import requests
import json
import os
from datetime import datetime
import pytz

TOKEN = st.secrets["TEAMSNAP_TOKEN"]
TEAM_ID = 10574989
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BASE = "https://api.teamsnap.com/v3"
GOALS_FILE = os.path.join(os.path.dirname(__file__), "goals.json")

def get_data(url):
    r = requests.get(url, headers=HEADERS)
    items = r.json().get("collection", {}).get("items", [])
    return [{d["name"]: d["value"] for d in item["data"]} for item in items]

def load_goals() -> dict:
    if not os.path.exists(GOALS_FILE):
        return {}
    with open(GOALS_FILE) as f:
        return json.load(f)

def save_goals(data: dict):
    with open(GOALS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def parse_dt(dt_str):
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    mt = pytz.timezone("America/Denver")
    return dt.astimezone(mt)

def fmt_dt(dt):
    """Cross-platform datetime formatting without leading zeros."""
    return dt.strftime(f"%a %b {dt.day}, %Y · {dt.hour % 12 or 12}:{dt.strftime('%M')} {'AM' if dt.hour < 12 else 'PM'}")

def fmt_time(dt):
    return f"{dt.hour % 12 or 12}:{dt.strftime('%M')} {'AM' if dt.hour < 12 else 'PM'}"

st.set_page_config(page_title="2013 Girls (Harman) Dashboard", page_icon="⚽", layout="wide")


st.title("⚽ 2013 Girls (Harman) — Team Dashboard")
st.caption("New Frontier Soccer · U13 Formation Phase · Season 2026")

# --- LOAD DATA ---
with st.spinner("Loading team data..."):
    members = get_data(f"{BASE}/members/search?team_id={TEAM_ID}")
    events = get_data(f"{BASE}/events/search?team_id={TEAM_ID}")
    availabilities = get_data(f"{BASE}/availabilities/search?team_id={TEAM_ID}")
    opponents = get_data(f"{BASE}/opponents/search?team_id={TEAM_ID}")

players = [m for m in members if not m.get("is_non_player")]
staff = [m for m in members if m.get("is_non_player")]
opponent_map = {str(o["id"]): o.get("name", "Unknown") for o in opponents}

now = datetime.now(pytz.timezone("America/Denver"))
upcoming = sorted(
    [e for e in events if e.get("start_date") and parse_dt(e["start_date"]) >= now],
    key=lambda e: parse_dt(e["start_date"])
)
past = sorted(
    [e for e in events if e.get("start_date") and parse_dt(e["start_date"]) < now],
    key=lambda e: parse_dt(e["start_date"]), reverse=True
)

# --- TOP METRICS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("👧 Players", len(players))
col2.metric("📅 Upcoming Events", len(upcoming))
col3.metric("✅ Events Completed", len(past))
col4.metric("🏟️ Opponents", len(opponents))

st.divider()

# --- UPCOMING SCHEDULE ---
left, right = st.columns([2, 1])

with left:
    st.subheader("📅 Upcoming Schedule")
    if not upcoming:
        st.info("No upcoming events.")
    for e in upcoming[:8]:
        dt = parse_dt(e["start_date"])
        arrive_dt = parse_dt(e.get("arrival_date") or e["start_date"])
        opponent_name = opponent_map.get(str(e.get("opponent_id")), "") if e.get("opponent_id") else ""
        label = "🎮 Game" if e.get("is_game") else "🏃 Practice" if e.get("name") == "Training" else "📌 Event"
        title_suffix = f" vs {opponent_name}" if opponent_name else f" — {e.get('name', '')}"
        canceled = " ~~CANCELED~~" if e.get("is_canceled") else ""
        with st.expander(f"{label}{title_suffix}{canceled} · {fmt_dt(dt)}"):
            if opponent_name:
                st.write(f"**Opponent:** {opponent_name}")
            st.write(f"**Location:** {e.get('location_name', 'TBD')}")
            if e.get("additional_location_details"):
                st.write(f"**Field:** {e['additional_location_details']}")
            st.write(f"**Arrive by:** {fmt_time(arrive_dt)}")
            st.write(f"**Duration:** {e.get('duration_in_minutes', '?')} minutes")
            if e.get("notes"):
                st.write(f"**Notes:** {e['notes']}")

            # Availability for this event
            event_avail = [a for a in availabilities if str(a.get("event_id")) == str(e["id"])]
            going = [a for a in event_avail if a.get("status_code") == 1]
            not_going = [a for a in event_avail if a.get("status_code") in (0, 2)]
            no_response = [a for a in event_avail if a.get("status_code") is None]
            st.write(f"**Availability:** ✅ {len(going)} going · ❌ {len(not_going)} not going · ⬜ {len(no_response)} no response")

# --- ROSTER ---
with right:
    st.subheader("👧 Player Roster")
    for p in sorted(players, key=lambda x: x.get("last_name") or ""):
        jersey = f" #{p['jersey_number']}" if p.get("jersey_number") else ""
        position = f" · {p['position']}" if p.get("position") else ""
        st.write(f"**{p['first_name']} {p['last_name']}**{jersey}{position}")

    st.divider()
    st.subheader("🧑‍💼 Team Staff")
    for s in staff:
        role = "Owner" if s.get("is_owner") else "Manager"
        st.write(f"{s['first_name']} {s['last_name']} · {role}")

st.divider()

# --- NEXT 3 EVENTS AVAILABILITY DETAIL ---
st.subheader("📋 Availability Detail")
status_label = {1: "✅ Going", 2: "❌ Not Going", 0: "❌ Not Going", None: "⬜ No Response"}
for event in upcoming[:3]:
    event_dt = parse_dt(event["start_date"])
    label = "🎮 Game" if event.get("is_game") else "🏃 Practice" if event.get("name") == "Training" else "📌 Event"
    with st.expander(f"{label} — {event.get('name')} · {event_dt.strftime('%a %b')} {event_dt.day}", expanded=True):
        event_avail = {str(a["member_id"]): a.get("status_code") for a in availabilities if str(a.get("event_id")) == str(event["id"])}
        cols = st.columns(4)
        for i, p in enumerate(sorted(players, key=lambda x: x.get("last_name") or "")):
            status = event_avail.get(str(p["id"]))
            cols[i % 4].write(f"{status_label.get(status, '⬜')} {p['first_name']} {p['last_name']}")

st.divider()

# --- GOAL TRACKER ---
# Goals stored locally in goals.json as {event_id: {member_id: goals}}
st.subheader("⚽ Goal Tracker")

all_goals = load_goals()  # {event_id: {member_id: int}}
player_map = {str(p["id"]): p for p in players}

# --- LEADERBOARD ---
player_totals: dict[str, int] = {}
for game_goals in all_goals.values():
    for mid, g in game_goals.items():
        player_totals[mid] = player_totals.get(mid, 0) + g

if player_totals:
    st.markdown("**Season Goals Leaderboard**")
    sorted_scorers = sorted(player_totals.items(), key=lambda x: x[1], reverse=True)
    lboard_cols = st.columns(min(len(sorted_scorers), 5))
    for i, (mid, total) in enumerate(sorted_scorers):
        p = player_map.get(mid, {})
        name = f"{p.get('first_name', '?')} {p.get('last_name', '')}"
        lboard_cols[i % 5].metric(name, f"{total} ⚽")

    st.markdown("**Season Goal Scorers**")
    table_data = [
        {"#": i + 1, "Player": f"{player_map.get(mid, {}).get('first_name', '?')} {player_map.get(mid, {}).get('last_name', '')}".strip(), "Goals": total}
        for i, (mid, total) in enumerate(sorted_scorers)
    ]
    st.table(table_data)
else:
    st.info("No goals recorded yet for this season.")

st.divider()

# --- PER-GAME SCORERS ---
games = [e for e in past if e.get("is_game")]
games_with_goals = [g for g in games if all_goals.get(str(g["id"]))]
if games_with_goals:
    st.markdown("**Goals by Game**")
    for g in games_with_goals:
        game_id = str(g["id"])
        opp = opponent_map.get(str(g.get("opponent_id")), "") if g.get("opponent_id") else ""
        title = f"vs {opp}" if opp else g.get("name", "Game")
        dt = parse_dt(g["start_date"])
        scorers = sorted(all_goals[game_id].items(), key=lambda x: x[1], reverse=True)
        with st.expander(f"🎮 {title} · {dt.strftime('%b')} {dt.day}"):
            for mid, n in scorers:
                p = player_map.get(mid, {})
                name = f"{p.get('first_name', '?')} {p.get('last_name', '')}"
                st.write(f"{'⚽' * n}  **{name}** — {n} goal{'s' if n > 1 else ''}")

st.divider()

# --- RECORD GOALS FORM ---
if not games:
    st.info("No completed games found to record goals for.")
else:
    with st.expander("📝 Record Goals for a Game", expanded=False):
        def game_label(g):
            opp = opponent_map.get(str(g.get("opponent_id")), "") if g.get("opponent_id") else ""
            suffix = f"vs {opp}" if opp else g.get("name", "Game")
            return f"{fmt_dt(parse_dt(g['start_date']))} — {suffix}"
        game_options = {game_label(g): g for g in games}
        selected_label = st.selectbox("Select game", list(game_options.keys()))
        selected_game = game_options[selected_label]
        game_id = str(selected_game["id"])

        existing_for_game: dict[str, int] = all_goals.get(game_id, {})

        st.markdown("Enter goals scored (leave 0 for players who didn't score):")
        goal_inputs: dict[str, int] = {}
        input_cols = st.columns(3)
        for i, p in enumerate(sorted(players, key=lambda x: x.get("last_name") or "")):
            mid = str(p["id"])
            name = f"{p['first_name']} {p['last_name']}"
            goal_inputs[mid] = input_cols[i % 3].number_input(
                name, min_value=0, max_value=20, value=existing_for_game.get(mid, 0), key=f"goals_{mid}"
            )

        if st.button("💾 Save Goals"):
            all_goals[game_id] = {mid: g for mid, g in goal_inputs.items() if g > 0}
            save_goals(all_goals)
            st.success("Goals saved!")
            st.rerun()

st.divider()
st.caption(f"Last refreshed: {now.strftime('%B')} {now.day}, {now.year} at {fmt_time(now)} Mountain Time · Data from TeamSnap API")
