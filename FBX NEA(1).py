import tkinter as tk
import sqlite3
from tkinter import ttk, messagebox

# Make the window
root = tk.Tk()
root.title("FBX")
root.geometry("800x600")

# Game settings - MUCH BIGGER for full screen
WIDTH = 1920  # Increased from 1400
HEIGHT = 1080  # Increased from 800
PLAYER_SIZE = 80  # Increased from 60
BALL_SIZE = 32  # Increased from 24
PLAYER_SPEED = 12  # Increased from 8 (to cover more distance)

# Game variables
ball_dx = 0
ball_dy = 0
score1 = 0
score2 = 0
game_on = False
keys_pressed = set()

# ===============================================================
# DATABASE MODULE
# ===============================================================

class GameDatabase:
    def __init__(self, db_name="fbx_stats.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        """Create necessary database tables if they don't exist"""
        # Players table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                goals_scored INTEGER DEFAULT 0,
                goals_conceded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Matches table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER,
                player2_id INTEGER,
                player1_score INTEGER,
                player2_score INTEGER,
                winner_id INTEGER,
                match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player1_id) REFERENCES players (id),
                FOREIGN KEY (player2_id) REFERENCES players (id),
                FOREIGN KEY (winner_id) REFERENCES players (id)
            )
        ''')
        
        # Insert default players if they don't exist
        default_players = [("Player 1",), ("Player 2",)]
        for player in default_players:
            self.cursor.execute('''
                INSERT OR IGNORE INTO players (name) VALUES (?)
            ''', player)
        
        self.conn.commit()
    
    def record_match(self, player1_name, player2_name, score1, score2):
        """Record a completed match in the database"""
        try:
            # Get player IDs
            player1_id = self.get_player_id(player1_name)
            player2_id = self.get_player_id(player2_name)
            
            # Determine winner
            if score1 > score2:
                winner_id = player1_id
                # Update player stats
                self.update_player_stats(player1_id, True, score1, score2)
                self.update_player_stats(player2_id, False, score2, score1)
            elif score2 > score1:
                winner_id = player2_id
                # Update player stats
                self.update_player_stats(player2_id, True, score2, score1)
                self.update_player_stats(player1_id, False, score1, score2)
            else:
                winner_id = None  # Draw
            
            # Insert match record
            self.cursor.execute('''
                INSERT INTO matches 
                (player1_id, player2_id, player1_score, player2_score, winner_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (player1_id, player2_id, score1, score2, winner_id))
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error recording match: {e}")
            return False
    
    def get_player_id(self, name):
        """Get player ID by name, create if doesn't exist"""
        self.cursor.execute("SELECT id FROM players WHERE name = ?", (name,))
        result = self.cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # Create new player
            self.cursor.execute("INSERT INTO players (name) VALUES (?)", (name,))
            self.conn.commit()
            return self.cursor.lastrowid
    
    def update_player_stats(self, player_id, won, goals_scored, goals_conceded):
        """Update player statistics after a match"""
        if won:
            self.cursor.execute('''
                UPDATE players 
                SET wins = wins + 1, 
                    goals_scored = goals_scored + ?,
                    goals_conceded = goals_conceded + ?
                WHERE id = ?
            ''', (goals_scored, goals_conceded, player_id))
        else:
            self.cursor.execute('''
                UPDATE players 
                SET losses = losses + 1, 
                    goals_scored = goals_scored + ?,
                    goals_conceded = goals_conceded + ?
                WHERE id = ?
            ''', (goals_scored, goals_conceded, player_id))
        self.conn.commit()
    
    def get_leaderboard(self, limit=10):
        """Get top players by win rate"""
        self.cursor.execute('''
            SELECT name, wins, losses, goals_scored, goals_conceded,
                   CASE 
                       WHEN (wins + losses) > 0 
                       THEN ROUND((wins * 100.0) / (wins + losses), 1)
                       ELSE 0
                   END as win_rate
            FROM players
            WHERE (wins + losses) > 0
            ORDER BY win_rate DESC, wins DESC
            LIMIT ?
        ''', (limit,))
        
        return self.cursor.fetchall()
    
    def get_recent_matches(self, limit=5):
        """Get recent match history"""
        self.cursor.execute('''
            SELECT 
                p1.name as player1_name,
                p2.name as player2_name,
                m.player1_score,
                m.player2_score,
                pw.name as winner_name,
                strftime('%Y-%m-%d %H:%M', m.match_date) as match_date
            FROM matches m
            JOIN players p1 ON m.player1_id = p1.id
            JOIN players p2 ON m.player2_id = p2.id
            LEFT JOIN players pw ON m.winner_id = pw.id
            ORDER BY m.match_date DESC
            LIMIT ?
        ''', (limit,))
        
        return self.cursor.fetchall()
    
    def get_player_stats(self, player_name):
        """Get detailed statistics for a specific player"""
        self.cursor.execute('''
            SELECT 
                name,
                wins,
                losses,
                goals_scored,
                goals_conceded,
                CASE 
                    WHEN (wins + losses) > 0 
                    THEN ROUND((wins * 100.0) / (wins + losses), 1)
                    ELSE 0
                END as win_rate
            FROM players
            WHERE name = ?
        ''', (player_name,))
        
        return self.cursor.fetchone()
    
    def close(self):
        """Close database connection"""
        self.conn.close()

# Initialize database
db = GameDatabase()

# ===============================================================
# STATISTICS WINDOW FUNCTIONS
# ===============================================================

def show_statistics():
    """Display game statistics in a new window"""
    stats_window = tk.Toplevel(root)
    stats_window.title("FBX Statistics")
    stats_window.geometry("700x550")
    stats_window.configure(bg="lightgray")
    
    # Create notebook for tabs
    notebook = ttk.Notebook(stats_window)
    
    # Leaderboard tab
    leaderboard_frame = tk.Frame(notebook, bg="white")
    notebook.add(leaderboard_frame, text="🏆 Leaderboard")
    
    # Recent matches tab
    matches_frame = tk.Frame(notebook, bg="white")
    notebook.add(matches_frame, text="📅 Recent Matches")
    
    # Player stats tab
    player_frame = tk.Frame(notebook, bg="white")
    notebook.add(player_frame, text="👤 Player Stats")
    
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Populate leaderboard
    tk.Label(leaderboard_frame, text="TOP PLAYERS LEADERBOARD", 
             font=("Arial", 18, "bold"), bg="white", fg="blue").pack(pady=15)
    
    leaderboard = db.get_leaderboard()
    
    if leaderboard:
        # Header
        header_frame = tk.Frame(leaderboard_frame, bg="lightblue")
        header_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        headers = ["Rank", "Player", "Wins", "Losses", "Win Rate", "Goals"]
        for i, header in enumerate(headers):
            tk.Label(header_frame, text=header, font=("Arial", 11, "bold"), 
                    bg="lightblue", width=12 if i > 0 else 6).grid(row=0, column=i, padx=2)
        
        # Player rows
        for i, (name, wins, losses, goals_scored, goals_conceded, win_rate) in enumerate(leaderboard):
            row_frame = tk.Frame(leaderboard_frame, bg="white" if i % 2 == 0 else "lightgray")
            row_frame.pack(fill="x", padx=20, pady=2)
            
            # Rank with medal emoji
            if i == 0:
                rank_text = "🥇"
            elif i == 1:
                rank_text = "🥈"
            elif i == 2:
                rank_text = "🥉"
            else:
                rank_text = f"{i+1}."
            
            tk.Label(row_frame, text=rank_text, font=("Arial", 11), 
                    bg=row_frame["bg"], width=6).grid(row=0, column=0)
            tk.Label(row_frame, text=name, font=("Arial", 11), 
                    bg=row_frame["bg"], width=12).grid(row=0, column=1)
            tk.Label(row_frame, text=str(wins), font=("Arial", 11), 
                    bg=row_frame["bg"], width=12).grid(row=0, column=2)
            tk.Label(row_frame, text=str(losses), font=("Arial", 11), 
                    bg=row_frame["bg"], width=12).grid(row=0, column=3)
            tk.Label(row_frame, text=f"{win_rate}%", font=("Arial", 11), 
                    bg=row_frame["bg"], fg="green" if win_rate > 50 else "red", 
                    width=12).grid(row=0, column=4)
            tk.Label(row_frame, text=f"{goals_scored}-{goals_conceded}", font=("Arial", 11), 
                    bg=row_frame["bg"], width=12).grid(row=0, column=5)
    else:
        tk.Label(leaderboard_frame, text="No matches played yet!", 
                font=("Arial", 14), bg="white", fg="gray").pack(pady=50)
    
    # Populate recent matches
    tk.Label(matches_frame, text="RECENT MATCH HISTORY", 
             font=("Arial", 18, "bold"), bg="white", fg="blue").pack(pady=15)
    
    matches = db.get_recent_matches()
    
    if matches:
        # Header
        header_frame = tk.Frame(matches_frame, bg="lightblue")
        header_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        headers = ["Date", "Match", "Score", "Winner"]
        for i, header in enumerate(headers):
            tk.Label(header_frame, text=header, font=("Arial", 11, "bold"), 
                    bg="lightblue", width=15 if i > 0 else 20).grid(row=0, column=i, padx=2)
        
        # Match rows
        for i, (p1_name, p2_name, score1, score2, winner, match_date) in enumerate(matches):
            row_frame = tk.Frame(matches_frame, bg="white" if i % 2 == 0 else "lightgray")
            row_frame.pack(fill="x", padx=20, pady=2)
            
            tk.Label(row_frame, text=match_date, font=("Arial", 10), 
                    bg=row_frame["bg"], width=20).grid(row=0, column=0)
            tk.Label(row_frame, text=f"{p1_name} vs {p2_name}", font=("Arial", 10), 
                    bg=row_frame["bg"], width=15).grid(row=0, column=1)
            tk.Label(row_frame, text=f"{score1} - {score2}", font=("Arial", 10, "bold"), 
                    bg=row_frame["bg"], width=15).grid(row=0, column=2)
            
            winner_color = "blue" if winner == "Player 1" else "red" if winner == "Player 2" else "gray"
            winner_text = winner if winner else "Draw"
            tk.Label(row_frame, text=winner_text, font=("Arial", 10, "bold"), 
                    bg=row_frame["bg"], fg=winner_color, width=15).grid(row=0, column=3)
    else:
        tk.Label(matches_frame, text="No matches played yet!", 
                font=("Arial", 14), bg="white", fg="gray").pack(pady=50)
    
    # Populate player stats
    tk.Label(player_frame, text="PLAYER STATISTICS", 
             font=("Arial", 18, "bold"), bg="white", fg="blue").pack(pady=15)
    
    # Player 1 stats
    player1_stats = db.get_player_stats("Player 1")
    player2_stats = db.get_player_stats("Player 2")
    
    stats_frame = tk.Frame(player_frame, bg="white")
    stats_frame.pack(pady=20)
    
    if player1_stats:
        name, wins, losses, goals_scored, goals_conceded, win_rate = player1_stats
        player1_frame = tk.Frame(stats_frame, bg="lightblue", relief="ridge", borderwidth=2)
        player1_frame.grid(row=0, column=0, padx=20, pady=10)
        
        tk.Label(player1_frame, text="PLAYER 1 (Blue)", font=("Arial", 16, "bold"), 
                bg="lightblue", fg="blue").pack(pady=10)
        
        stats_text = f"""Wins: {wins}
Losses: {losses}
Win Rate: {win_rate}%
Goals Scored: {goals_scored}
Goals Conceded: {goals_conceded}
Goal Difference: {goals_scored - goals_conceded}"""
        
        tk.Label(player1_frame, text=stats_text, font=("Arial", 12), 
                bg="lightblue", justify="left").pack(pady=10, padx=20)
    
    if player2_stats:
        name, wins, losses, goals_scored, goals_conceded, win_rate = player2_stats
        player2_frame = tk.Frame(stats_frame, bg="pink", relief="ridge", borderwidth=2)
        player2_frame.grid(row=0, column=1, padx=20, pady=10)
        
        tk.Label(player2_frame, text="PLAYER 2 (Red)", font=("Arial", 16, "bold"), 
                bg="pink", fg="red").pack(pady=10)
        
        stats_text = f"""Wins: {wins}
Losses: {losses}
Win Rate: {win_rate}%
Goals Scored: {goals_scored}
Goals Conceded: {goals_conceded}
Goal Difference: {goals_scored - goals_conceded}"""
        
        tk.Label(player2_frame, text=stats_text, font=("Arial", 12), 
                bg="pink", justify="left").pack(pady=10, padx=20)
    
    # Close button
    tk.Button(stats_window, text="Close", font=("Arial", 14), 
             command=stats_window.destroy, bg="red", fg="white",
             width=15).pack(pady=20)

def show_stats_button():
    """Add a stats button after game ends (called from check_goal)"""
    # Check if button already exists
    for item in canvas.find_all():
        if canvas.type(item) == "window":
            canvas.delete(item)
    
    # Create stats button
    stats_btn = tk.Button(canvas, text="📊 View Statistics", 
                         font=("Arial", 24, "bold"),
                         bg="yellow", fg="black",
                         command=show_statistics,
                         relief="raised", borderwidth=3)
    
    # Place button on canvas
    canvas.create_window(WIDTH/2, HEIGHT/2 + 100, window=stats_btn)

# ===============================================================
# GAME FUNCTIONS (ORIGINAL CODE WITH DATABASE INTEGRATION)
# ===============================================================

# --------------------------
# CREATE THE MENU
# --------------------------
def make_menu():
    # Menu frame - fill entire window
    menu_frame = tk.Frame(root, bg="green")
    menu_frame.pack(fill="both", expand=True)
    
    # Center everything
    center_frame = tk.Frame(menu_frame, bg="green")
    center_frame.place(relx=0.5, rely=0.5, anchor="center")
    
    # Title
    title = tk.Label(center_frame, text="FBX", font=("Arial", 72, "bold"), fg="blue", bg="green")
    title.pack(pady=50)
    
    # Play button
    play_btn = tk.Button(center_frame, text="PLAY", font=("Arial", 36), width=12, 
                        bg="white", fg="black", borderwidth=4, command=start_game)
    play_btn.pack(pady=20)
    
    # Stats button
    stats_btn = tk.Button(center_frame, text="📊 STATISTICS", font=("Arial", 28), width=15,
                         bg="lightblue", fg="black", borderwidth=4, command=show_statistics)
    stats_btn.pack(pady=20)
    
    # Make buttons change color when mouse is over them
    def on_play_enter(e):
        play_btn.config(bg="black", fg="white")
    
    def on_play_leave(e):
        play_btn.config(bg="white", fg="black")
    
    def on_stats_enter(e):
        stats_btn.config(bg="blue", fg="white")
    
    def on_stats_leave(e):
        stats_btn.config(bg="lightblue", fg="black")
    
    play_btn.bind("<Enter>", on_play_enter)
    play_btn.bind("<Leave>", on_play_leave)
    stats_btn.bind("<Enter>", on_stats_enter)
    stats_btn.bind("<Leave>", on_stats_leave)
    
    return menu_frame

# --------------------------
# CREATE THE GAME
# --------------------------
def make_game():
    # Game frame
    game_frame = tk.Frame(root)
    
    # Canvas for drawing - FULL SCREEN_SIZE
    canvas = tk.Canvas(game_frame, width=WIDTH, height=HEIGHT, bg="green")
    canvas.pack()
    
    # Draw stands (top and bottom) - BIGGER
    stand_height = 80  # Increased from 50
    canvas.create_rectangle(0, 0, WIDTH, stand_height, fill="gray")
    canvas.create_rectangle(0, HEIGHT-stand_height, WIDTH, HEIGHT, fill="gray")
    
    # Field area - BIGGER
    field_top = stand_height
    field_bottom = HEIGHT - stand_height
    middle_y = (field_top + field_bottom) / 2
    
    # Draw field lines - BIGGER
    canvas.create_line(WIDTH/2, field_top, WIDTH/2, field_bottom, fill="white", width=4)  # Thicker
    canvas.create_oval(WIDTH/2-120, middle_y-120, WIDTH/2+120, middle_y+120,  # Bigger circle
                      outline="white", width=4)  # Thicker
    
    # Draw goals - BIGGER
    goal_width = 80  # Increased from 50
    goal_height = 300  # Increased from 200
    canvas.create_rectangle(0, middle_y-goal_height/2, goal_width, middle_y+goal_height/2,
                          fill="white", outline="black", width=4)  # Thicker outline
    canvas.create_rectangle(WIDTH-goal_width, middle_y-goal_height/2, WIDTH, middle_y+goal_height/2,
                          fill="white", outline="black", width=4)  # Thicker outline
    
    # Draw players - BIGGER
    player1 = canvas.create_rectangle(150, middle_y-PLAYER_SIZE/2,  # Start further from edge
                                     150+PLAYER_SIZE, middle_y+PLAYER_SIZE/2,
                                     fill="blue", outline="black", width=3)  # Thicker outline
    player2 = canvas.create_rectangle(WIDTH-150-PLAYER_SIZE, middle_y-PLAYER_SIZE/2,
                                     WIDTH-150, middle_y+PLAYER_SIZE/2,
                                     fill="red", outline="black", width=3)  # Thicker outline
    
    # Draw ball - BIGGER
    ball = canvas.create_oval(WIDTH/2-BALL_SIZE/2, middle_y-BALL_SIZE/2,
                            WIDTH/2+BALL_SIZE/2, middle_y+BALL_SIZE/2,
                            fill="white")
    
    # Score_text - BIGGER
    score_text = canvas.create_text(WIDTH/2, stand_height/2, text="0 - 0",
                                   font=("Arial", 48, "bold"), fill="white")  # Bigger font
    
    return game_frame, canvas, player1, player2, ball, score_text

# ===============================================================
# GAME FUNCTIONS
# ===============================================================

def update_score():
    canvas.itemconfig(score_text, text=f"{score1} - {score2}")

def check_goal():
    global score1, score2, game_on, ball_dx, ball_dy
    
    if not game_on:
        return
    
    # Get ball position
    bx1, by1, bx2, by2 = canvas.coords(ball)
    
    # Field position
    field_top = 80  # Updated to match new stand height
    field_bottom = HEIGHT - 80
    middle_y = (field_top + field_bottom) / 2
    goal_width = 80  # Updated
    goal_height = 300  # Updated
    
    # Check if ball is in left goal
    if bx1 <= goal_width and by1 >= middle_y-goal_height/2 and by2 <= middle_y+goal_height/2:
        score2 += 1
        update_score()
        reset_players()
        canvas.create_text(WIDTH/2, middle_y, text="GOAL! Player 2 Scores!",
                          font=("Arial", 64, "bold"), fill="yellow", tags="msg")  # Bigger font
        root.after(1500, lambda: canvas.delete("msg"))
    
    # Check if ball is in right goal
    elif bx2 >= WIDTH-goal_width and by1 >= middle_y-goal_height/2 and by2 <= middle_y+goal_height/2:
        score1 += 1
        update_score()
        reset_players()
        canvas.create_text(WIDTH/2, middle_y, text="GOAL! Player 1 Scores!",
                          font=("Arial", 64, "bold"), fill="yellow", tags="msg")  # Bigger font
        root.after(1500, lambda: canvas.delete("msg"))
    
    # Check if someone won
    if score1 >= 5:
        game_on = False
        # Record the match in database
        db.record_match("Player 1", "Player 2", score1, score2)
        
        canvas.create_text(WIDTH/2, middle_y, text="PLAYER 1 WINS!",
                          font=("Arial", 80, "bold"), fill="blue", tags="win")  # Bigger font
        root.after(2000, show_stats_button)  # Show stats button after win
        root.after(5000, go_to_menu)
    elif score2 >= 5:
        game_on = False
        # Record the match in database
        db.record_match("Player 1", "Player 2", score1, score2)
        
        canvas.create_text(WIDTH/2, middle_y, text="PLAYER 2 WINS!",
                          font=("Arial", 80, "bold"), fill="red", tags="win")  # Bigger font
        root.after(2000, show_stats_button)  # Show stats button after win
        root.after(5000, go_to_menu)

def reset_players():
    global ball_dx, ball_dy
    
    # Field position
    field_top = 80  # Updated
    field_bottom = HEIGHT - 80
    middle_y = (field_top + field_bottom) / 2
    
    # Put ball in middle
    canvas.coords(ball, WIDTH/2-BALL_SIZE/2, middle_y-BALL_SIZE/2,
                  WIDTH/2+BALL_SIZE/2, middle_y+BALL_SIZE/2)
    
    ball_dx = 0
    ball_dy = 0
    
    # Put players back
    canvas.coords(player1, 150, middle_y-PLAYER_SIZE/2,  # Updated position
                  150+PLAYER_SIZE, middle_y+PLAYER_SIZE/2)
    canvas.coords(player2, WIDTH-150-PLAYER_SIZE, middle_y-PLAYER_SIZE/2,
                  WIDTH-150, middle_y+PLAYER_SIZE/2)

def key_down(event):
    # Fix for Caps Lock: convert to lowercase for WASD keys
    key = event.keysym
    if key in ["W", "A", "S", "D"]:  # Caps Lock versions
        key = key.lower()  # Convert to lowercase
    keys_pressed.add(key)

def key_up(event):
    key = event.keysym
    if key in ["W", "A", "S", "D"]:  # Caps Lock versions
        key = key.lower()  # Convert to lowercase
    keys_pressed.discard(key)

def can_move(player, dx, dy, other_player):
    """Check if a player can move without overlapping the other player"""
    # Get current positions
    px1, py1, px2, py2 = canvas.coords(player)
    ox1, oy1, ox2, oy2 = canvas.coords(other_player)
    
    # Calculate new position
    new_x1 = px1 + dx
    new_y1 = py1 + dy
    new_x2 = px2 + dx
    new_y2 = py2 + dy
    
    # Check boundaries (updated for bigger field)
    if new_x1 < 0 or new_x2 > WIDTH or new_y1 < 80 or new_y2 > HEIGHT-80:  # 80 = stand_height
        return False
    
    # Check if new position overlaps with other player
    if (new_x1 < ox2 and new_x2 > ox1 and new_y1 < oy2 and new_y2 > oy1):
        return False  # Would overlap
    
    return True  # Can move

def move_players():
    if not game_on:
        root.after(16, move_players)
        return
    
    # Move Player 1 (WASD) - works with lowercase AND uppercase (Caps Lock)
    # Check each direction separately
    if ("w" in keys_pressed or "W" in keys_pressed) and can_move(player1, 0, -PLAYER_SPEED, player2):
        canvas.move(player1, 0, -PLAYER_SPEED)
    if ("s" in keys_pressed or "S" in keys_pressed) and can_move(player1, 0, PLAYER_SPEED, player2):
        canvas.move(player1, 0, PLAYER_SPEED)
    if ("a" in keys_pressed or "A" in keys_pressed) and can_move(player1, -PLAYER_SPEED, 0, player2):
        canvas.move(player1, -PLAYER_SPEED, 0)
    if ("d" in keys_pressed or "D" in keys_pressed) and can_move(player1, PLAYER_SPEED, 0, player2):
        canvas.move(player1, PLAYER_SPEED, 0)
    
    # Move Player 2 (Arrow keys)
    if "Up" in keys_pressed and can_move(player2, 0, -PLAYER_SPEED, player1):
        canvas.move(player2, 0, -PLAYER_SPEED)
    if "Down" in keys_pressed and can_move(player2, 0, PLAYER_SPEED, player1):
        canvas.move(player2, 0, PLAYER_SPEED)
    if "Left" in keys_pressed and can_move(player2, -PLAYER_SPEED, 0, player1):
        canvas.move(player2, -PLAYER_SPEED, 0)
    if "Right" in keys_pressed and can_move(player2, PLAYER_SPEED, 0, player1):
        canvas.move(player2, PLAYER_SPEED, 0)
    
    # Check if players hit the ball
    check_ball_hit(player1)
    check_ball_hit(player2)
    
    root.after(16, move_players)

def check_ball_hit(player):
    global ball_dx, ball_dy
    
    # Get player position
    px1, py1, px2, py2 = canvas.coords(player)
    
    # Get ball position
    bx1, by1, bx2, by2 = canvas.coords(ball)
    
    # Check if player touches ball
    if (px1 < bx2 and px2 > bx1 and py1 < by2 and py2 > by1):
        # Push ball away
        ball_middle_x = (bx1 + bx2) / 2
        ball_middle_y = (by1 + by2) / 2
        player_middle_x = (px1 + px2) / 2
        player_middle_y = (py1 + py2) / 2
        
        push_x = ball_middle_x - player_middle_x
        push_y = ball_middle_y - player_middle_y
        
        # Make the push consistent
        length = (push_x**2 + push_y**2)**0.5
        if length > 0:
            push_x = push_x / length * 4  # Increased from 3 for bigger field
            push_y = push_y / length * 4  # Increased from 3 for bigger field
        
        ball_dx += push_x
        ball_dy += push_y

def move_ball():
    global ball_dx, ball_dy
    
    if game_on:
        # Move the ball
        canvas.move(ball, ball_dx, ball_dy)
        
        # Get ball position
        bx1, by1, bx2, by2 = canvas.coords(ball)
        
        # Bounce off walls (updated for bigger field)
        if bx1 <= 0:
            canvas.move(ball, 0 - bx1, 0)
            ball_dx = -ball_dx * 0.6
        
        if bx2 >= WIDTH:
            canvas.move(ball, WIDTH - bx2, 0)
            ball_dx = -ball_dx * 0.6
        
        if by1 <= 80:  # 80 = stand height
            canvas.move(ball, 0, 80 - by1)
            ball_dy = -ball_dy * 0.6
        
        if by2 >= HEIGHT-80:  # 80 = stand height
            canvas.move(ball, 0, HEIGHT-80 - by2)
            ball_dy = -ball_dy * 0.6
        
        # Check for goals
        check_goal()
        
        # Slow down the ball (slightly less friction for bigger field)
        ball_dx = ball_dx * 0.90  # 0.88 - 0.90 (less friction)
        ball_dy = ball_dy * 0.90  # 0.88 - 0.90 (less friction)
        
        # Stop if moving very slowly
        if abs(ball_dx) < 0.1:
            ball_dx = 0
        if abs(ball_dy) < 0.1:
            ball_dy = 0
    
    root.after(20, move_ball)

# ===============================================================
# SCREEN SWITCHING
# ===============================================================
def start_game():
    global score1, score2, game_on, menu_frame, game_frame
    global canvas, player1, player2, ball, score_text
    
    # Reset scores
    score1 = 0
    score2 = 0
    game_on = True
    
    # Hide menu
    menu_frame.pack_forget()
    
    # Create game if first time
    if 'game_frame' not in globals():
        game_frame, canvas, player1, player2, ball, score_text = make_game()
    
    # Show game - FULL SCREEN
    root.attributes('-fullscreen', True)  # Make it full screen
    game_frame.pack(fill="both", expand=True)
    
    # Set up keyboard - include uppercase for Caps Lock
    keys = ["w", "a", "s", "d", "W", "A", "S", "D", "Up", "Down", "Left", "Right"]
    for key in keys:
        root.bind(f"<KeyPress-{key}>", key_down)
        root.bind(f"<KeyRelease-{key}>", key_up)
    
    # Escape key to exit full screen
    root.bind("<Escape>", lambda e: go_to_menu())
    
    canvas.focus_set()
    update_score()
    move_players()
    move_ball()
    reset_players()

def go_to_menu():
    global game_on, menu_frame, game_frame
    
    game_on = False
    
    # Exit full screen
    root.attributes('-fullscreen', False)
    root.geometry("800x600")
    
    # Hide game
    if 'game_frame' in globals():
        game_frame.pack_forget()
    
    # Show menu
    menu_frame.pack(fill="both", expand=True)
    
    # Remove keyboard binds
    keys = ["w", "a", "s", "d", "W", "A", "S", "D", "Up", "Down", "Left", "Right"]
    for key in keys:
        root.unbind(f"<KeyPress-{key}>")
        root.unbind(f"<KeyRelease-{key}>")
    
    # Remove escape key bind
    root.unbind("<Escape>")

# ===============================================================
# START THE GAME
# ===============================================================
# Create menu
menu_frame = make_menu()

# Start with menu
go_to_menu()

# Run the game
root.mainloop()

# Close database when game exits
db.close()
