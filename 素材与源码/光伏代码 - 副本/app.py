from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import secrets
from datetime import date, datetime, timedelta
import re
import pulp
import pandas as pd

app = Flask(__name__)
secret_key = secrets.token_hex(32)
app.secret_key = secret_key

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        port=3306,
        database="solar_db",
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_station_info():
    user_id = session.get('user_id')
    role = session.get('role')

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

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

    if user and user['password']==password :
        session['username'] = username
        session['user_id'] = user["user_id"]
        session['role'] = role["role"]
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
    record  = cursor.fetchall()
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
        rows = cursor.fetchall()  # 结果数据
        cols = [desc[0] for desc in cursor.description]  # 列名
        df = pd.DataFrame(list(rows), columns=cols)  # 构建 DataFrame
        return df
    finally:
        conn.close()

def data_prepare(station_id):
    sql = "SELECT * FROM `solar_data` WHERE ID = %s"
    df_power = fetch_df(sql, params=(station_id,))

    sql = "SELECT * FROM `power_storage` WHERE ID = %s"
    df_user = fetch_df(sql, params=(station_id,))
    target = '2025-07-02'
    # target = date.today() + timedelta(days=1)
    target_date = pd.to_datetime(target).date()
    df_power['时间'] = pd.to_datetime(df_power['时间'])

    df_power = df_power[df_power['时间'].dt.date == target_date]

    df_power['mdhm'] = pd.to_datetime(df_power["时间"]).dt.strftime('%m-%d %H:%M')
    df_user['mdhm'] = pd.to_datetime(df_user["时间"]).dt.strftime('%m-%d %H:%M')

    # df_user = df_user.set_index('time')
    result = df_user[df_user['mdhm'].isin(df_power['mdhm'])]

    use = result['用电功率'].tolist()

    power = df_power['预测发电功率'].tolist()
    t = range(96)
    load_demand = dict(zip(t, use))
    # 加载光伏数据
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
    # 上网电价
    sell_price = 0.391

    # 电网功率变量（可正可负）
    P_grid = pulp.LpVariable.dicts("P_grid", time_horizon, lowBound=None, cat='Continuous')

    Q_plus = pulp.LpVariable.dicts("Q_plus", time_horizon, lowBound=0, cat='Continuous')  # 购电功率
    Q_minus = pulp.LpVariable.dicts("Q_minus", time_horizon, lowBound=0, cat='Continuous')  # 售电功率
    I = pulp.LpVariable.dicts("I", time_horizon, cat='Binary')  # 二进制变量
    # 当前充放电功率
    P_storage = pulp.LpVariable.dicts("P_storage", time_horizon, lowBound=None, cat='Continuous')
    # 决策变量Q_t，反映当前时刻的储能电量
    Q_t = pulp.LpVariable.dicts("Q_t", time_horizon, lowBound=None, cat='Continuous')

    M = 1000000  # 足够大的正数

    for t in time_horizon:
        model += (P_grid[t] + pv_generation[t] + P_storage[t] == load_demand[t])

    # 线性化约束
    for t in time_horizon:
        model += Q_plus[t] <= I[t] * M
        model += Q_plus[t] <= P_grid[t] + (1 - I[t]) * M
        model += Q_plus[t] >= P_grid[t] - (1 - I[t]) * M
        model += Q_minus[t] <= (1 - I[t]) * M
        model += Q_minus[t] <= -P_grid[t] + I[t] * M
        model += Q_minus[t] >= -P_grid[t] - I[t] * M

    # 储能电量动态约束
    initial_soc = 0  # 初始储能电量(kWh)，可以根据需要调整或设为变量
    model += Q_t[0] == initial_soc
    # p_max = 5000 * 0.1  # 最大出力
    # q_max = p_max * 4  # 储能容量
    # 储能电量变化：Q_{t+1} = Q_t - P_storage[t] * delta_t
    for t in range(95):  # t从0到94
        model += Q_t[t + 1] == Q_t[t] - P_storage[t] * delta_t

    # 循环约束：Q_{96} = Q_0（一个周期后储能恢复）
    model += Q_t[95] - P_storage[95] * delta_t == initial_soc

    for t in time_horizon:
        # 放电不能超过当前电量：P_storage[t] * delta_t <= Q_t[t]
        model += P_storage[t] * delta_t <= Q_t[t]
        model += P_storage[t] <= p_max
        model += P_storage[t] >= -p_max
        model += Q_t[t] <= q_max

    # 总成本 = 购电成本 - 售电收入
    total_cost = (pulp.lpSum([buy_price[t] * Q_plus[t] * delta_t for t in time_horizon]) -
                  pulp.lpSum([sell_price * Q_minus[t] * delta_t for t in time_horizon]))

    model += total_cost
    # solver = pulp.PULP_CBC_CMD(msg=False)
    # model.solve(solver)
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
                '实际放电功率': P_storage[t].varValue,
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

    station_id = session.get('station_id', station_info[0]['ID'])

    # now_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    now_time = '2025-07-01 09:00:00'
    end_time = now_time.split(" ")[0] + " 00:00:00"

    conn = get_db_connection()
    cursor = conn.cursor()
    # 查询后一周的数据
    # sql = """
    #     SELECT * FROM solar_data
    #     WHERE ID = %s AND 时间 BETWEEN %s AND DATE_ADD(%s, INTERVAL 7 DAY)
    #     ORDER BY 时间
    # """
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

    # 单位换算
    for data in data_list:
        data["时间"] = data["时间"].strftime("%Y-%m-%d %H:%M:%S")
    if not data_list:
        flash('该发电站数据尚未更新', 'danger')

    scale_a = request.args.get('scale_a', '0.1')
    scale_b = request.args.get('scale_b', '2')
    scale_a=float(scale_a)
    scale_b=float(scale_b)

    for station in station_info:
        if station['ID'] == station_id:
            found_station = station
            break

    if found_station:
        p_max = found_station['装机容量']*scale_a
    q_max = p_max * scale_b

    load_demand, pv_generation, buy_price = data_prepare(station_id)
    if len(load_demand) == 0:
        results, opted_cost, raw_cost= {},0,0
    else:
        results, opted_cost, raw_cost = storage_solver(buy_price, load_demand, pv_generation, p_max, q_max)

    return render_template("weather_power.html", data_list=data_list, station_info=station_info, station_id=station_id, now_data=now_data,results=results, opted_cost=opted_cost, raw_cost=raw_cost, p_max=p_max, q_max=q_max)

# 局部更新：储能建议（第四页）数据
@app.route('/storage_section')
def storage_section():
    if 'username' not in session:
        return jsonify({"error": "not_login"}), 401

    station_info = get_station_info()
    station_id = session.get('station_id', station_info[0]['ID'])

    # 参数（默认与页面一致）
    scale_a = float(request.args.get('scale_a', '0.1'))
    scale_b = float(request.args.get('scale_b', '2'))

    # 找到当前电站
    found_station = next((s for s in station_info if s['ID'] == station_id), None)
    if not found_station:
        return jsonify({"error": "station_not_found"}), 404

    p_max = found_station['装机容量'] * scale_a
    q_max = p_max * scale_b

    # 计算优化
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
        "save_cost": raw_cost - opted_cost,
        "results": results
    })

@app.route('/info')
def info():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    conn = get_db_connection()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT user_id, username FROM users")
    all_users = cursor.fetchall()
    conn.close()
    station_info = get_station_info()

    station_id = request.args.get('station_id', station_info[0]['ID'])  # 默认第一个电站

    selected = next((u for u in station_info if u['ID'] == station_id), station_info[0])
    return render_template("info.html", selected=selected, station_info=station_info, all_users=all_users)
@app.route('/user_manage')
def user_manage():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 查询用户及角色
        cursor.execute("""
            SELECT u.user_id, u.username, u.password, r.role
            FROM users u
            LEFT JOIN roles r ON u.user_id = r.user_id
        """)
        users_data = cursor.fetchall()

        # 查询用户对应的电站
        cursor.execute("SELECT user_id, ID FROM station_info")
        station_data = cursor.fetchall()

    # 将 station 按 user_id 归类到用户数据里
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
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("DELETE FROM station_info WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM roles WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'status': 'success', 'redirect_url': url_for('user_manage')})

@app.route('/update_user', methods=['POST'])
def update_user():
    user_id = request.form['id']
    new_password = request.form['password']
    new_role = request.form['role']

    conn = get_db_connection()
    with conn.cursor() as cursor:
        # 更新密码
        cursor.execute(
            "UPDATE users SET password = %s WHERE user_id = %s",
            (new_password, user_id)
        )
        # 更新或插入角色
        cursor.execute("SELECT COUNT(*) as cnt FROM roles WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        if result['cnt'] > 0:
            cursor.execute(
                "UPDATE roles SET role = %s WHERE user_id = %s",
                (new_role, user_id)
            )
        else:
            cursor.execute(
                "INSERT INTO roles (user_id, role) VALUES (%s, %s)",
                (user_id, new_role)
            )
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

    # 更新数据库
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
    cursor.close()
    conn.close()
    return redirect(url_for('info', station_id=station_id))

@app.route('/add_station', methods=['POST'])
def add_station():
    station_info = get_station_info()
    session_user_id = session.get('user_id')
    session_role = session.get('role')
    new_id = request.form['new_id']

    # 如果是管理员，允许指定 user_id；否则用自己的 user_id
    if session_role == 'admin':
        user_id = request.form.get('target_user_id')
        if not user_id:
            return "管理员必须选择用户", 400
    else:
        user_id = session_user_id

    # 检查 ID 是否已存在
    if any(u['ID'] == new_id for u in station_info):
        return "ID 已存在，请选择其他 ID", 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO station_info (ID, 装机容量, 经度, 纬度, 角度, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (new_id, 0.0, "120.74", "31.65", 1.0, user_id))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('info', station_id=new_id))

@app.route('/delete_station', methods=['POST'])
def delete_station():
    station_id = request.form['ID']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM station_info WHERE ID = %s", (station_id,))
    conn.commit()
    cursor.close()
    conn.close()

    # 如果删除的是当前站，重定向到第一个（如果还存在）
    return redirect(url_for('info'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)