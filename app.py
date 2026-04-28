import streamlit as st
import requests
from datetime import datetime
import pytz

TOKEN = st.secrets["TEAMSNAP_TOKEN"]
TEAM_ID = 10574989
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
CJSON_HEADERS = {**HEADERS, "Content-Type": "application/vnd.collection+json"}
BASE = "https://api.teamsnap.com/v3"

def get_data(url):
    r = requests.get(url, headers=HEADERS)
    items = r.json().get("collection", {}).get("items", [])
    return [{d["name"]: d["value"] for d in item["data"]} for item in items]

def post_data(url, fields: dict):
    payload = {"collection": {"template": {"data": [{"name": k, "value": v} for k, v in fields.items()]}}}
    return requests.post(url, headers=CJSON_HEADERS, json=payload)

def delete_data(url):
    return requests.delete(url, headers=HEADERS)

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

players = [m for m in members if not m.get("is_non_player")]
staff = [m for m in members if m.get("is_non_player")]

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
col4.metric("🏟️ Opponents", "8")

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
        label = "🎮 Game" if e.get("is_game") else "🏃 Practice" if e.get("name") == "Training" else "📌 Event"
        canceled = " ~~CANCELED~~" if e.get("is_canceled") else ""
        with st.expander(f"{label} — {fmt_dt(dt)} — {e.get('name', '')}{canceled}"):
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
            not_going = [a for a in event_avail if a.get("status_code") == 2]
            no_response = [a for a in event_avail if not a.get("status_code")]
            st.write(f"**Availability:** ✅ {len(going)} going · ❌ {len(not_going)} not going · ❓ {len(no_response)} no response")

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
status_label = {1: "✅ Going", 2: "❌ Not Going", None: "❓ No Response"}
for event in upcoming[:3]:
    event_dt = parse_dt(event["start_date"])
    label = "🎮 Game" if event.get("is_game") else "🏃 Practice" if event.get("name") == "Training" else "📌 Event"
    with st.expander(f"{label} — {event.get('name')} · {event_dt.strftime('%a %b')} {event_dt.day}", expanded=True):
        event_avail = {str(a["member_id"]): a.get("status_code") for a in availabilities if str(a.get("event_id")) == str(event["id"])}
        cols = st.columns(4)
        for i, p in enumerate(sorted(players, key=lambda x: x.get("last_name") or "")):
            status = event_avail.get(str(p["id"]))
            cols[i % 4].write(f"{status_label.get(status, '❓')} {p['first_name']} {p['last_name']}")

st.divider()

# --- GOAL TRACKER ---
st.subheader("⚽ Goal Tracker")

stat_defs = get_data(f"{BASE}/stat_defs/search?team_id={TEAM_ID}")
goals_def = next((s for s in stat_defs if s.get("name", "").lower() == "goals"), None)

if not goals_def:
    st.warning("No 'Goals' stat definition found for this team.")
    if st.button("Create 'Goals' stat definition"):
        r = post_data(f"{BASE}/stat_defs", {"team_id": TEAM_ID, "name": "Goals", "type": "integer", "sequence": 1})
        if r.ok:
            st.success("Created! Refresh the page to continue.")
        else:
            st.error(f"Error: {r.status_code} — {r.text}")
else:
    stat_entries = get_data(f"{BASE}/stat_entries/search?team_id={TEAM_ID}")

    # --- LEADERBOARD ---
    goals_def_id = str(goals_def["id"])
    goal_entries = [e for e in stat_entries if str(e.get("stat_def_id")) == goals_def_id]
    player_goals: dict[str, int] = {}
    for e in goal_entries:
        mid = str(e.get("member_id"))
        player_goals[mid] = player_goals.get(mid, 0) + int(e.get("value") or 0)

    if player_goals:
        st.markdown("**Season Goals Leaderboard**")
        player_map = {str(p["id"]): p for p in players}
        sorted_scorers = sorted(player_goals.items(), key=lambda x: x[1], reverse=True)
        lboard_cols = st.columns(min(len(sorted_scorers), 5))
        for i, (mid, total) in enumerate(sorted_scorers):
            p = player_map.get(mid, {})
            name = f"{p.get('first_name', '?')} {p.get('last_name', '')}"
            lboard_cols[i % 5].metric(name, f"{total} ⚽")
    else:
        st.info("No goals recorded yet for this season.")

    st.divider()

    # --- RECORD GOALS FORM ---
    games = [e for e in past if e.get("is_game")]
    if not games:
        st.info("No completed games found to record goals for.")
    else:
        with st.expander("📝 Record Goals for a Game", expanded=False):
            game_options = {f"{fmt_dt(parse_dt(g['start_date']))} — {g.get('name', 'Game')}": g for g in games}
            selected_label = st.selectbox("Select game", list(game_options.keys()))
            selected_game = game_options[selected_label]
            game_id = str(selected_game["id"])

            existing_for_game = {
                str(e["member_id"]): e
                for e in goal_entries
                if str(e.get("event_id")) == game_id
            }

            st.markdown("Enter goals scored (leave 0 for players who didn't score):")
            goal_inputs: dict[str, int] = {}
            input_cols = st.columns(3)
            for i, p in enumerate(sorted(players, key=lambda x: x.get("last_name") or "")):
                existing_val = int(existing_for_game.get(str(p["id"]), {}).get("value") or 0)
                name = f"{p['first_name']} {p['last_name']}"
                goal_inputs[str(p["id"])] = input_cols[i % 3].number_input(
                    name, min_value=0, max_value=20, value=existing_val, key=f"goals_{p['id']}"
                )

            if st.button("💾 Save Goals"):
                errors = []
                saved = 0
                for member_id, goals in goal_inputs.items():
                    existing = existing_for_game.get(member_id)
                    existing_val = int(existing.get("value") or 0) if existing else 0
                    if existing and goals != existing_val:
                        # update: delete old, post new (API v3 has no PATCH for stat_entries)
                        delete_data(f"{BASE}/stat_entries/{existing['id']}")
                        if goals > 0:
                            r = post_data(f"{BASE}/stat_entries", {
                                "stat_def_id": goals_def["id"], "member_id": member_id,
                                "event_id": game_id, "value": goals,
                            })
                            if not r.ok:
                                errors.append(f"member {member_id}: {r.status_code}")
                            else:
                                saved += 1
                    elif not existing and goals > 0:
                        r = post_data(f"{BASE}/stat_entries", {
                            "stat_def_id": goals_def["id"], "member_id": member_id,
                            "event_id": game_id, "value": goals,
                        })
                        if not r.ok:
                            errors.append(f"member {member_id}: {r.status_code}")
                        else:
                            saved += 1
                if errors:
                    st.error(f"Some entries failed: {', '.join(errors)}")
                else:
                    st.success(f"Saved! {saved} goal record(s) updated. Refresh to see the leaderboard.")

st.divider()
st.caption(f"Last refreshed: {now.strftime('%B')} {now.day}, {now.year} at {fmt_time(now)} Mountain Time · Data from TeamSnap API")
