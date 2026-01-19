import pandas as pd
import requests
import argparse
import sys
import json
import os
import time

# Constants
TBA_KEY = "8SgFtkRYDT4Awkv91ZkQOohs26hwGjfXlgW9ZQDhbARU49Qlh3da1DRof3GYyaBS"
AI_PROXY_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
AI_PROXY_KEY = "sk-hc-v1-43124d1d0caf4b8f8e88206ec8ab0460608380551c094293a6d7489cb6deac5d"
CSV_PATH = "6377 Waco Scouting - Scouting_waco.csv"

class DataHandler:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.df = self._load_data()

    def _load_data(self):
        if not os.path.exists(self.csv_path):
            print(f"Error: CSV file not found at {self.csv_path}")
            sys.exit(1)
        
        try:
            df = pd.read_csv(self.csv_path)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            sys.exit(1)
            
        # Filter strictly for match data (ignore non-match entries if any)
        if 'match_number' not in df.columns:
            print("Error: 'match_number' column missing in CSV.")
            sys.exit(1)
            
        # Clean/Impute Data
        cols_to_fill_zero = [
            'auto_coral_l1', 'auto_coral_l2', 'auto_coral_l3', 'auto_coral_l4',
            'tele_coral_l1', 'tele_coral_l2', 'tele_coral_l3', 'tele_coral_l4',
            'auto_algae_processor', 'tele_algae_processor', 'defender_rating'
        ]
        
        for col in cols_to_fill_zero:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                df[col] = 0 # If metric missing, assume 0
                
        # Parse 'tele_climb_speed' for success rate (Any non-failure text = success)
        # "No", "No Attempt", "0" -> 0, anything else (Fast, Slow, etc) -> 1
        def parse_climb(val):
            s = str(val).lower().strip()
            if s in ['no', 'no attempt', '0', 'nan', 'none']:
                return 0
            return 1
        
        if 'tele_climb_speed' in df.columns:
            df['climb_success'] = df['tele_climb_speed'].apply(parse_climb)
        else:
            df['climb_success'] = 0

        # Parse 'auto_moved'
        def parse_auto_move(val):
            s = str(val).lower().strip()
            return 1 if s == 'yes' else 0
            
        if 'auto_moved' in df.columns:
            df['auto_moved_score'] = df['auto_moved'].apply(parse_auto_move)
        else:
            df['auto_moved_score'] = 0

        # Ensure 'frc_team' is string of number
        df['frc_team'] = df['frc_team'].astype(str).str.replace('frc', '', case=False)
        
        # Sort by match number
        df = df.sort_values(by='match_number')
        
        return df

    def get_historical_data(self, match_n):
        """Returns dataframe with matches < match_n"""
        return self.df[self.df['match_number'] < match_n]

    def get_average_stats(self, team, historic_df):
        """Calculates aggregates for a specific team using historic_df"""
        team_stats = historic_df[historic_df['frc_team'] == str(team)]
        
        if team_stats.empty:
            return {
                "avg_auto_coral": 0,
                "avg_tele_coral": 0,
                "avg_coral_l1": 0,
                "avg_coral_l4": 0,
                "avg_algae_processed": 0,
                "avg_defender_rating": 0,
                "climb_rate": "0%",
                "auto_moved_rate": "0%"
            }
        
        # Aggregates
        avg_coral_l1 = (team_stats['auto_coral_l1'] + team_stats['tele_coral_l1']).mean()
        avg_coral_l4 = (team_stats['auto_coral_l4'] + team_stats['tele_coral_l4']).mean()
        avg_algae = (team_stats['auto_algae_processor'] + team_stats['tele_algae_processor']).mean()
        avg_defender = team_stats['defender_rating'].mean()
        
        # New Stats
        avg_auto_coral = (team_stats['auto_coral_l1'] + team_stats['auto_coral_l2'] + 
                          team_stats['auto_coral_l3'] + team_stats['auto_coral_l4']).mean()
        avg_tele_coral = (team_stats['tele_coral_l1'] + team_stats['tele_coral_l2'] + 
                          team_stats['tele_coral_l3'] + team_stats['tele_coral_l4']).mean()
        
        climb_rate = team_stats['climb_success'].mean() * 100
        auto_move_rate = team_stats['auto_moved_score'].mean() * 100
        
        return {
            "avg_auto_coral": round(avg_auto_coral, 2),
            "avg_tele_coral": round(avg_tele_coral, 2),
            "avg_coral_l1": round(avg_coral_l1, 2),
            "avg_coral_l4": round(avg_coral_l4, 2),
            "avg_algae_processed": round(avg_algae, 2),
            "avg_defender_rating": round(avg_defender, 2),
            "climb_rate": f"{round(climb_rate, 1)}%",
            "auto_moved_rate": f"{round(auto_move_rate, 1)}%"
        }
        
    def get_actual_result(self, match_n):
        """Returns the actual result row for Match N if available (for comparison)"""
        match_data = self.df[self.df['match_number'] == match_n]
        if match_data.empty:
            return None
        return match_data

class TBAClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.thebluealliance.com/api/v3"
        self.headers = {"X-TBA-Auth-Key": self.api_key}

    def get_match_schedule(self, event_key, match_number):
        return None 

    def get_teams_for_match(self, event_key, match_number):
        match_key = f"{event_key}_qm{match_number}"
        url = f"{self.base_url}/match/{match_key}"
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                red_teams = [t.replace('frc', '') for t in data['alliances']['red']['team_keys']]
                blue_teams = [t.replace('frc', '') for t in data['alliances']['blue']['team_keys']]
                return {"red": red_teams, "blue": blue_teams}
            else:
                print(f"TBA API Error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            print(f"TBA API Exception: {e}")
            return None

class AIProxyClient:
    def __init__(self, api_key, model="google/gemini-3.0-pro"):
        self.api_key = api_key
        self.model = model
        self.url = AI_PROXY_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def get_strategy(self, prompt):
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            resp = requests.post(self.url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                # Assuming standard OpenAI format which Gemini Flash on Hack Club Proxy should follow
                return resp.json()['choices'][0]['message']['content']
            else:
                return f"Error: {resp.status_code} - {resp.text}"
        except Exception as e:
            return f"Error: {e}"

class StrategyEngine:
    def __init__(self, data_handler, tba_client, ai_client):
        self.data = data_handler
        self.tba = tba_client
        self.ai = ai_client

    def simulate_match(self, match_n, alliance="blue"):
        alliance = "red" if alliance.lower() in ["red", "r"] else "blue"
        opponent = "blue" if alliance == "red" else "red"
        
        print(f"--- Simulating Strategy for Match {match_n} ({alliance.upper()} Alliance) ---")
        
        # Get Event Key from CSV (taking first row's event key)
        if self.data.df['event_key'].empty:
             print("Error: No event_key found in CSV.")
             return
        event_key = self.data.df['event_key'].iloc[0]
        
        # 1. Get Teams for Match N
        teams = self.tba.get_teams_for_match(event_key, match_n)
        if not teams:
            print(f"TBA lookup failed. Attempting to infer teams from CSV for Match {match_n}...")
            match_rows = self.data.df[self.data.df['match_number'] == match_n]
            if match_rows.empty:
                print(f"No data found for match {match_n} in CSV or TBA.")
                return
            
            red_teams = []
            blue_teams = []
            
            for _, row in match_rows.iterrows():
                ds = str(row['driver_station']).lower()
                team = str(row['frc_team'])
                if 'red' in ds:
                    red_teams.append(team)
                elif 'blue' in ds:
                    blue_teams.append(team)
            
            teams = {"red": red_teams, "blue": blue_teams}
            
        print(f"Red Alliance: {teams['red']}")
        print(f"Blue Alliance: {teams['blue']}")
        
        # 2. Get Historical Stats (Matches 1 to N-1)
        historic_df = self.data.get_historical_data(match_n)
        
        red_stats = {}
        for team in teams['red']:
            red_stats[team] = self.data.get_average_stats(team, historic_df)
            
        blue_stats = {}
        for team in teams['blue']:
            blue_stats[team] = self.data.get_average_stats(team, historic_df)

        # 3. Construct Prompt
        prompt = self._construct_prompt(match_n, teams, red_stats, blue_stats, alliance)
        
        # 4. Get AI Strategy
        print("\nRequesting Strategy Advisor (Gemini 3.0 Flash)...")
        strategy = self.ai.get_strategy(prompt)
        print("\n=== AI Strategy Advisor Recommendation ===")
        print(strategy)
        
        # 5. Compare with Actual Result
        self._print_actual_comparison(match_n, teams)

    def _construct_prompt(self, match_n, teams, red_stats, blue_stats, target_alliance):
        prompt = f"Analyze Match {match_n} for the 2025 FRC Game Reefscape.\n"
        prompt += f"Red Alliance: {teams['red']}\n"
        prompt += f"Blue Alliance: {teams['blue']}\n\n"
        
        prompt += "Team Historical Stats (Prior to this match):\n"
        
        prompt += "--- RED ALLIANCE ---\n"
        for team, stats in red_stats.items():
            prompt += f"Team {team}: {stats}\n"
            
        prompt += "\n--- BLUE ALLIANCE ---\n"
        for team, stats in blue_stats.items():
            prompt += f"Team {team}: {stats}\n"
            
    def _construct_prompt(self, match_n, teams, red_stats, blue_stats, target_alliance):
        prompt = f"Analyze Match {match_n} for the 2025 FRC Game Reefscape.\n"
        prompt += f"Red Alliance: {teams['red']}\n"
        prompt += f"Blue Alliance: {teams['blue']}\n\n"
        
        prompt += "Team Historical Stats (Prior to this match):\n"
        
        prompt += "--- RED ALLIANCE ---\n"
        for team, stats in red_stats.items():
            prompt += f"Team {team}: {stats}\n"
            
        prompt += "\n--- BLUE ALLIANCE ---\n"
        for team, stats in blue_stats.items():
            prompt += f"Team {team}: {stats}\n"
            
        prompt += "\nIMPORTANT GAME RULES & CONSTRAINTS:"
        prompt += """Here is the strategic breakdown of the scoring and rules for REEFSCAPE℠, reformatted for easier reading without the chart.

1. Autonomous Period (First 15 Seconds)
In the first 15 seconds, robots operate on pre-programmed instructions. Scoring here is slightly more valuable than in Teleop to encourage automation.

Leave (3 Points): Awarded if your robot completely leaves its starting zone. This is critical because all three robots must do this to earn the Auto RP later.

Coral on L1 / Trough (3 Points): The lowest scoring location.

Coral on L2 (4 Points): Requires modest elevation.

Coral on L3 (6 Points): A significant jump in value.

Coral on L4 (7 Points): The highest possible score for a single game piece. This is the hardest target.

Algae in Processor (6 Points): High value, but usually reserved for Teleop to trigger bonuses.

Algae in Net (4 Points): Can be scored by robots or human players.

2. Teleop Period (Remaining 2 Minutes 15 Seconds)
Drivers take control. The primary cycle involves driving to the Human Player station to get Coral, then driving to the Reef to score it.

Coral Scoring (The Primary Grind)

L1 / Trough (2 Points): Fast and easy, but low value. Used mainly to fill the Reef for Ranking Points.

L2 Branch (3 Points): Slightly better than L1, often accessible by simple arm mechanisms.

L3 Branch (4 Points): The "sweet spot" for competitive robots.

L4 Branch (5 Points): The maximum Teleop score for Coral. Winning teams usually specialize in hitting this level consistently.

Algae Scoring (The "Blockers" & Bonuses) Algae starts the match blocking the Reef branches. You must remove it to score Coral there. Once you have the Algae, you have two options:

Processor (6 Points): This scores points and passes the Algae to your Human Player. It is also required to activate the "Coopertition" bonus (lowering the RP threshold).

Net (4 Points): This is a pure scoring target. Robots can shoot Algae here, or Human Players can throw it here after receiving it from the Processor.

3. Endgame (Final Actions)
In the last 30 seconds (or whenever you are ready), robots return to the "Barge" area to hang or park.

Park (2 Points): Simply stopping in the Barge Zone. Useful only as a last resort or tie-breaker.

Shallow Cage Hang (6 Points): Hanging from the lower chain. Easier to reach but worth less.

Deep Cage Hang (12 Points): Hanging from the higher chain. This is the most valuable single action in the endgame. Securing a Deep Hang is often essential to getting the Barge Ranking Point.

Strategic Rules & Notes
Ranking Points (RP) Checklist In Qualification matches, you are fighting for 4 Ranking Points, not just the win.

Auto RP: All 3 robots must move (Leave), and the alliance must score at least 1 Coral during Auto.

Coral RP: You need to score 5 Coral on every level (L1, L2, L3, L4).

Strategic Exception: If both alliances score 2 Algae in their Processors (Coopertition), you only need 5 Coral on 3 levels (ignoring L4 usually).

Barge RP: Your alliance needs 14+ Endgame Points. This typically requires at least one Deep Cage Hang (12 pts) plus a Park (2 pts).

Win RP: 3 Points for winning the match.

Critical Field Rules

Algae Blocking: You generally cannot place Coral on a branch if Algae is currently sitting on it. You must "descore" the Algae first.

Extension Limits: You are allowed to extend your arm high only when you are in the Reef Zone (scoring). When you are driving across the field, you must retract your lift to a lower height (approx. 4ft) to avoid tipping or hitting field elements.

Protected Zones: Your opponents cannot touch you while you are in your Reef Zone (scoring) or your Barge Zone (hanging). Drawing a foul here gives you free points."""
        
        prompt += f"\nCore Task: Recommend a winning strategy for the **{target_alliance.upper()} ALLIANCE**.\n"
        prompt += f"1. Should {target_alliance.upper()} prioritize securing Ranking Points (likely via 4+ Co-opertition/Coral thresholds or Climbing) or just maximizing total points for the Win? Explain the trade-off based on their stats vs the opponents. If clear underdogs, prioritize RPs.\n"
        prompt += "2. **Defense Strategy**: Who on the opposing alliance is the biggest threat? Assign ONE robot to defend them if necessary, considering the 1-defender rule. Who is the best defender on our alliance?\n"
        prompt += "3. **Scoring Focus**: precise balance of L1-L4 Coral cycling vs Algae Processing (removing Algae to enable scoring).\n"
        prompt += "Provide a concise, tactical response addressed to the Drive Coach."
        prompt += f"Only focus on {target_alliance.upper()} alliance for scoring strategy. Do not consider the opposing alliance unless we are talking about defence or whos going to win"
        prompt += "Algae clearing is only needed for L2 and L3"
        return prompt


    def _print_actual_comparison(self, match_n, teams):
        print("\n--- Actual Result (Oracle) ---")
        match_rows = self.data.df[self.data.df['match_number'] == match_n]
        if match_rows.empty:
            print("Match has not happened relative to dataset.")
            return

        # Simple summary of what actually happened
        for _, row in match_rows.iterrows():
            team = str(row['frc_team'])
            l4 = row['auto_coral_l4'] + row['tele_coral_l4']
            algae = row['auto_algae_processor'] + row['tele_algae_processor']
            print(f"Team {team}: Scored {l4} L4 Coral, Processed {algae} Algae.")

def main():
    parser = argparse.ArgumentParser(description="FRC Reefscape AI Strategy Advisor")
    parser.add_argument("--match", type=int, required=True, help="Match number to simulate strategy for")
    parser.add_argument("--alliance", type=str, choices=['red', 'blue', 'r', 'b'], default='blue', help="Alliance to generate strategy for (r/red or b/blue)")
    args = parser.parse_args()

    data_handler = DataHandler(CSV_PATH)
    tba_client = TBAClient(TBA_KEY)
    ai_client = AIProxyClient(AI_PROXY_KEY)
    
    engine = StrategyEngine(data_handler, tba_client, ai_client)
    engine.simulate_match(args.match, args.alliance)

if __name__ == "__main__":
    main()
