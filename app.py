from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import secrets
from datetime import date, datetime, timedelta
import re
import pulp
import pandas as pd
import os

# 根据环境自动选择数据库驱动
if os.environ.get('DATABASE_URL'):
    # Railway 环境：使用 PostgreSQL
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_DRIVER = 'psycopg2'
    print("使用 PostgreSQL 数据库驱动（云端部署）")
else:
    # 本地开发环境：使用 MySQL
    import pymysql
    DB_DRIVER = 'pymysql'
    print("使用 MySQL 数据库驱动（本地开发）")

app = Flask(__name__)
secret_key = secrets.token_hex(32)
app.secret_key = secret_key

def get_db_connection():
    """获取数据库连接，自动适配云端和本地环境"""
    if DB_DRIVER == 'psycopg2':
        # Railway 环境：使用 PostgreSQL
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise RuntimeError("DATABASE_URL 环境变量未设置。请在Railway上添加PostgreSQL数据库。")
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    else:
        # 本地开发：使用 MySQL
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='solar_db',
            port=3306,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    return conn

def get_station_info():
    user_id = session.get('user_id')
    role = session.get('role')

    conn = get_db_connection()
    cursor = conn.cursor()

    if role == 'admin':
        cursor.execute("SELECT * FROM station_info ORDER BY 创建时间 ASC")
    else:
        cursor.execute("SELECT * FROM station_info WHERE user_id = %s ORDER BY 创建时间 ASC", (user_id,))

    station_info = cursor.fetchall()
    conn.close()
    return station_info

@app.route('/get_station_info')
def get_station_info_route():
    station_info = get_station_info()
    return jsonify(station_info)

@app.route('/set_station', methods=['POST'])
def set_station():
    station_id = request.form.get('station_id')
    if station_id:
        session["station_id"] = station_id
    return redirect(request.referrer or url_for('weather_power'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    if user is not None:
        cursor.execute("SELECT * FROM roles WHERE user_id = %s", (user["user_id"],))
        role = cursor.fetchone()
    conn.close()

    if user and user['password']==password:
        session['username'] = username
        session['user_id'] = user["user_id"]
        session['role'] = role["role"] if role else 'viewer'
        flash('登录成功', 'success')
    else:
        flash('用户名或密码错误', 'danger')
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    new_id = request.form['new_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. 检查用户名是否已存在
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    if cursor.fetchone():
        flash('用户名已存在', 'warning')
        conn.close()
        return redirect(url_for('user_manage'))

    # 2. 检查电站ID是否已存在
    cursor.execute("SELECT * FROM station_info WHERE ID = %s", (new_id,))
    if cursor.fetchone():
        flash('电站ID已存在，请使用其他ID', 'warning')
        conn.close()
        return redirect(url_for('user_manage'))

    # 3. 执行插入操作
    if DB_DRIVER == 'psycopg2':
        # PostgreSQL: 使用 RETURNING 获取自增ID
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s) RETURNING user_id", (username, password))
        user_id = cursor.fetchone()['user_id']
    else:
        # MySQL: 使用 lastrowid
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
        user_id = cursor.lastrowid

    cursor.execute("INSERT INTO roles (user_id, role) VALUES (%s, %s)", (user_id, 'viewer'))

    cursor.execute("""
        INSERT INTO station_info (ID, 装机容量, 经度, 纬度, 角度, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (new_id, 0.0, "120.74", "31.65", 1.0, user_id))

    conn.commit()
    flash('注册成功', 'success')
    conn.close()

    return redirect(url_for('user_manage'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('role', None)
    session.pop('station_id', None)
    flash('已退出登录', 'info')
    return redirect(url_for('home'))

@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT 年月,预测发电量 FROM hole_city""")
    record = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("index.html", record=record)

@app.route("/contaction")
def contaction():
    return render_template("contaction.html")

@app.route("/introduction")
def introduction():
    return render_template("introduction.html")

def fetch_df(sql, params=None):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        df = pd.DataFrame(list(rows), columns=cols)
        return df
    finally:
        conn.close()

def data_prepare(station_id):
    sql = "SELECT * FROM solar_data WHERE ID = %s"
    df_power = fetch_df(sql, params=(station_id,))

    sql = "SELECT * FROM power_storage WHERE ID = %s"
    df_user = fetch_df(sql, params=(station_id,))
    
    target = '2025-07-02'
    target_date = pd.to_datetime(target).date()
    
    if not df_power.empty:
        df_power['时间'] = pd.to_datetime(df_power['时间'])
        df_power = df_power[df_power['时间'].dt.date == target_date]
        df_power['mdhm'] = pd.to_datetime(df_power["时间"]).dt.strftime('%m-%d %H:%M')
    
    if not df_user.empty:
        df_user['时间'] = pd.to_datetime(df_user['时间'])
        df_user['mdhm'] = pd.to_datetime(df_user["时间"]).dt.strftime('%m-%d %H:%M')

    result = pd.DataFrame()
    if not df_user.empty and not df_power.empty and 'mdhm' in df_user.columns and 'mdhm' in df_power.columns:
        result = df_user[df_user['mdhm'].isin(df_power['mdhm'])]
    
    use = result['用电功率'].tolist() if not result.empty else [0] * 96
    power = df_power['预测发电功率'].tolist() if not df_power.empty else [0] * 96
    
    if len(use) < 96:
        use = use + [0] * (96 - len(use))
    if len(power) < 96:
        power = power + [0] * (96 - len(power))
    
    t = range(96)
    load_demand = dict(zip(t, use))
    pv_generation = dict(zip(t, power))

    buy_price = {}
    for t in range(96):
        if 0 <= t < 32:
            buy_price[t] = 0.3139
        elif 32 <= t < 48 or 68 <= t < 84:
            buy_price[t] = 1.0697
        else:
            buy_price[t] = 0.6418

    return load_demand, pv_generation, buy_price

def cost_calculation(load_demand, pv_generation, buy_price):
    times = list(range(96))
    total_cost = 0
    for t in times:
        total_cost += (load_demand[t] - pv_generation[t]) * 0.25 * buy_price[t]
    return total_cost

def storage_solver(buy_price, load_demand, pv_generation, p_max, q_max):
    model = pulp.LpProblem("Energy_Storage_Scaling_Optimization", pulp.LpMinimize)

    time_horizon = list(range(96))
    delta_t = 0.25
    sell_price = 0.391

    P_grid = pulp.LpVariable.dicts("P_grid", time_horizon, lowBound=None, cat='Continuous')
    Q_plus = pulp.LpVariable.dicts("Q_plus", time_horizon, lowBound=0, cat='Continuous')
    Q_minus = pulp.LpVariable.dicts("Q_minus", time_horizon, lowBound=0, cat='Continuous')
    I = pulp.LpVariable.dicts("I", time_horizon, cat='Binary')
    P_storage = pulp.LpVariable.dicts("P_storage", time_horizon, lowBound=None, cat='Continuous')
    Q_t = pulp.LpVariable.dicts("Q_t", time_horizon, lowBound=None, cat='Continuous')

    M = 1000000

    for t in time_horizon:
        model += (P_grid[t] + pv_generation[t] + P_storage[t] == load_demand[t])

    for t in time_horizon:
        model += Q_plus[t] <= I[t] * M
        model += Q_plus[t] <= P_grid[t] + (1 - I[t]) * M
        model += Q_plus[t] >= P_grid[t] - (1 - I[t]) * M
        model += Q_minus[t] <= (1 - I[t]) * M
        model += Q_minus[t] <= -P_grid[t] + I[t] * M
        model += Q_minus[t] >= -P_grid[t] - I[t] * M

    initial_soc = 0
    model += Q_t[0] == initial_soc
    
    for t in range(95):
        model += Q_t[t + 1] == Q_t[t] - P_storage[t] * delta_t

    model += Q_t[95] - P_storage[95] * delta_t == initial_soc

    for t in time_horizon:
        model += P_storage[t] * delta_t <= Q_t[t]
        model += P_storage[t] <= p_max
        model += P_storage[t] >= -p_max
        model += Q_t[t] <= q_max

    total_cost = (pulp.lpSum([buy_price[t] * Q_plus[t] * delta_t for t in time_horizon]) -
                  pulp.lpSum([sell_price * Q_minus[t] * delta_t for t in time_horizon]))

    model += total_cost
    model.solve()
    
    raw_cost = cost_calculation(load_demand, pv_generation, buy_price)
    results = []
    
    if pulp.LpStatus[model.status] == "Optimal":
        for t in time_horizon:
            hour = t // 4
            minute = (t % 4) * 15
            time_str = f"{hour:02d}:{minute:02d}"

            results.append({
                '时间': time_str,
                '负荷': load_demand[t],
                '光伏': pv_generation[t],
                '实际放电功率': P_storage[t].varValue if P_storage[t].varValue is not None else 0,
            })
    else:
        print("未找到最优解。请检查输入数据。")
    
    return results, pulp.value(model.objective), raw_cost

@app.route('/weather_power')
def weather_power():
    if 'username' not in session:
        flash('请先登录', 'danger')
        return redirect(url_for('home'))

    station_info = get_station_info()
    
    if not station_info:
        flash('没有可用的电站', 'danger')
        return redirect(url_for('home'))
        
    station_id = session.get('station_id', station_info[0]['ID'])

    now_time = '2025-07-01 09:00:00'
    end_time = now_time.split(" ")[0] + " 00:00:00"

    conn = get_db_connection()
    cursor = conn.cursor()
    
    if DB_DRIVER == 'psycopg2':
        # PostgreSQL 版本的时间查询
        sql = """
            SELECT * FROM solar_data
            WHERE ID = %s 
            AND 时间 BETWEEN %s AND (%s::timestamp + interval '7 days')
            AND (
                EXTRACT(HOUR FROM 时间) BETWEEN 6 AND 17
                OR 
                (EXTRACT(HOUR FROM 时间) = 18 AND EXTRACT(MINUTE FROM 时间) = 0 AND EXTRACT(SECOND FROM 时间) = 0)
            )
            ORDER BY 时间
        """
    else:
        # MySQL 版本的时间查询
        sql = """
            SELECT * FROM solar_data
            WHERE ID = %s 
            AND 时间 BETWEEN %s AND DATE_ADD(%s, INTERVAL 7 DAY)
            AND (
                HOUR(时间) BETWEEN 6 AND 17
                OR 
                (HOUR(时间) = 18 AND MINUTE(时间) = 0 AND SECOND(时间) = 0)
            )
            ORDER BY 时间
        """
    
    cursor.execute(sql, (station_id, end_time, end_time))
    data_list = cursor.fetchall()

    sql = """
        SELECT * FROM solar_data
        WHERE ID = %s AND 时间 <= %s
        ORDER BY 时间 DESC
        LIMIT 1
    """
    cursor.execute(sql, (station_id, now_time))
    now_data = cursor.fetchone()

    cursor.close()
    conn.close()

    for data in data_list:
        if isinstance(data["时间"], str):
            data["时间"] = datetime.strptime(data["时间"], "%Y-%m-%d %H:%M:%S")
        data["时间"] = data["时间"].strftime("%Y-%m-%d %H:%M:%S")
        
    if not data_list:
        flash('该发电站数据尚未更新', 'warning')

    scale_a = float(request.args.get('scale_a', '0.1'))
    scale_b = float(request.args.get('scale_b', '2'))

    found_station = None
    for station in station_info:
        if station['ID'] == station_id:
            found_station = station
            break

    p_max = 0
    q_max = 0
    if found_station:
        p_max = found_station['装机容量'] * scale_a
        q_max = p_max * scale_b

    load_demand, pv_generation, buy_price = data_prepare(station_id)
    if len(load_demand) == 0:
        results, opted_cost, raw_cost = [], 0, 0
    else:
        results, opted_cost, raw_cost = storage_solver(buy_price, load_demand, pv_generation, p_max, q_max)

    return render_template("weather_power.html", 
                          data_list=data_list, 
                          station_info=station_info, 
                          station_id=station_id, 
                          now_data=now_data,
                          results=results, 
                          opted_cost=round(opted_cost, 2) if opted_cost else 0, 
                          raw_cost=round(raw_cost, 2) if raw_cost else 0, 
                          p_max=round(p_max, 2), 
                          q_max=round(q_max, 2))

@app.route('/storage_section')
def storage_section():
    if 'username' not in session:
        return jsonify({"error": "not_login"}), 401

    station_info = get_station_info()
    station_id = session.get('station_id', station_info[0]['ID'] if station_info else None)

    if not station_id:
        return jsonify({"error": "no_station"}), 404

    scale_a = float(request.args.get('scale_a', '0.1'))
    scale_b = float(request.args.get('scale_b', '2'))

    found_station = next((s for s in station_info if s['ID'] == station_id), None)
    if not found_station:
        return jsonify({"error": "station_not_found"}), 404

    p_max = found_station['装机容量'] * scale_a
    q_max = p_max * scale_b

    load_demand, pv_generation, buy_price = data_prepare(station_id)
    if len(load_demand) == 0:
        results, opted_cost, raw_cost = [], 0.0, 0.0
    else:
        results, opted_cost, raw_cost = storage_solver(buy_price, load_demand, pv_generation, p_max, q_max)

    return jsonify({
        "p_max": p_max,
        "q_max": q_max,
        "raw_cost": raw_cost,
        "opted_cost": opted_cost,
        "save_cost": raw_cost - opted_cost if opted_cost else 0,
        "results": results
    })

@app.route('/info')
def info():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users")
    all_users = cursor.fetchall()
    conn.close()
    
    station_info = get_station_info()

    station_id = request.args.get('station_id', station_info[0]['ID'] if station_info else None)
    selected = next((u for u in station_info if u['ID'] == station_id), station_info[0] if station_info else None)
    
    return render_template("info.html", selected=selected, station_info=station_info, all_users=all_users)

@app.route('/user_manage')
def user_manage():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT u.user_id, u.username, u.password, r.role
        FROM users u
        LEFT JOIN roles r ON u.user_id = r.user_id
    """)
    users_data = cursor.fetchall()

    cursor.execute("SELECT user_id, ID FROM station_info")
    station_data = cursor.fetchall()

    user_dict = {}
    for user in users_data:
        user['stations'] = []
        user_dict[user['user_id']] = user

    for row in station_data:
        uid = row['user_id']
        if uid in user_dict:
            user_dict[uid]['stations'].append(row['ID'])

    users = list(user_dict.values())
    conn.close()
    return render_template("user_manage.html", users=users)

@app.route('/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM station_info WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM roles WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'redirect_url': url_for('user_manage')})

@app.route('/update_user', methods=['POST'])
def update_user():
    user_id = request.form['id']
    new_password = request.form['password']
    new_role = request.form['role']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET password = %s WHERE user_id = %s", (new_password, user_id))
    
    cursor.execute("SELECT COUNT(*) as cnt FROM roles WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    if result['cnt'] > 0:
        cursor.execute("UPDATE roles SET role = %s WHERE user_id = %s", (new_role, user_id))
    else:
        cursor.execute("INSERT INTO roles (user_id, role) VALUES (%s, %s)", (user_id, new_role))
    
    conn.commit()
    conn.close()
    return redirect(url_for('user_manage'))

@app.route('/save_info', methods=['POST'])
def save_info():
    station_id = request.form['ID']
    capacity = float(request.form['capacity'])
    longitude = request.form['longitude']
    latitude = request.form['latitude']
    perspective = float(request.form['perspective'])
    fullname = request.form['fullname']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE station_info
        SET 装机容量 = %s,
            经度 = %s,
            纬度 = %s,
            角度 = %s,
            全称 = %s
        WHERE ID = %s
    """, (capacity, longitude, latitude, perspective, fullname, station_id))
    conn.commit()
    conn.close()
    return redirect(url_for('info', station_id=station_id))

@app.route('/add_station', methods=['POST'])
def add_station():
    station_info = get_station_info()
    session_user_id = session.get('user_id')
    session_role = session.get('role')
    new_id = request.form['new_id']

    if session_role == 'admin':
        user_id = request.form.get('target_user_id')
        if not user_id:
            return "管理员必须选择用户", 400
    else:
        user_id = session_user_id

    if any(u['ID'] == new_id for u in station_info):
        return "ID 已存在，请选择其他 ID", 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO station_info (ID, 装机容量, 经度, 纬度, 角度, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (new_id, 0.0, "120.74", "31.65", 1.0, user_id))
    conn.commit()
    conn.close()

    return redirect(url_for('info', station_id=new_id))

@app.route('/delete_station', methods=['POST'])
def delete_station():
    station_id = request.form['ID']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM station_info WHERE ID = %s", (station_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('info'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)