import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from keras.models import load_model
from pypinyin import lazy_pinyin
import xarray as xr
import pymysql

def chinese_to_pinyin(text):
    pinyin_list = lazy_pinyin(text)  # 不带声调
    return '_'.join(pinyin_list)

def data_clean(data):
    for i in range(len(data)):
        if i == 0 and (data[i] >= 2000 or data[i] < -1000):
            data[i] = 0
        if data[i] >= 2000 or data[i] < -1000:
            data[i] = data[i - 1]
    return data

def data_load(path):
    ds = xr.open_dataset(path)

    time_bytes = ds['time'].values

    time_format = "%Y-%m-%d_%H:%M:%S"
    beijing_times = []
    for t in time_bytes:
        # 解码字节字符串
        time_str = t.decode('utf-8')
        # 解析为 datetime 对象
        utc_time = datetime.strptime(time_str, time_format)
        # 转换为北京时间（UTC+8）
        beijing_time = utc_time + timedelta(hours=8)
        # 添加到结果列表
        beijing_times.append(beijing_time)

    temp = np.round(ds['T2'].values, 1)
    wind = np.round(ds['WS10'].values, 1)
    swddif = np.round(ds['SWDDIF'].values)
    swddir = np.round(ds['SWDDIR'].values)
    SWDD = np.round(ds['SWDDNI'].values) + swddif

    temp = data_clean(temp)
    wind = data_clean(wind)
    swddif = data_clean(swddif)
    swddir = data_clean(swddir)
    SWDD = data_clean(SWDD)

    data = {"时间": beijing_times, "温度": temp, "风速": wind,"总辐射": SWDD, "直接辐射": swddir, "散射辐射": swddif}
    df = pd.DataFrame(data)
    return df

def create_dataset(dataset, look_back=24):
    X = []
    for i in range(len(dataset) - look_back):
        X.append(dataset.iloc[i:(i + look_back), :])
    return np.array(X)

def power_pre(station_id):
    try:
        path = '../data/new_weather_data/CMA-WSP_ENERGY_BENJ_'
        today = datetime.now() - timedelta(days=1)
        yesterday = today - timedelta(days=1)

        # 检查并读取今天的文件
        today_file = path + today.strftime("%Y-%m-%d") + '.nc'
        if not os.path.exists(today_file):
            print("数据"+today_file+"丢失")
            return None
        df1 = data_load(today_file)

        # 检查并读取昨天的文件
        yesterday_file = path + yesterday.strftime("%Y-%m-%d") + '.nc'
        if not os.path.exists(yesterday_file):
            print("数据" + yesterday_file + "丢失")
            return None
        df2 = data_load(yesterday_file)

        # 合并数据
        df1_unique = df1[~df1['时间'].isin(df2['时间'])]
        df = pd.concat([df1_unique, df2], axis=0)

        data_clean = df.copy()
        del data_clean['时间']
        data = data_clean

        look_back = 48
        X = create_dataset(data, look_back)

        # 检查并加载模型
        model_path = os.path.normpath(chinese_to_pinyin(station_id) + '.h5')
        if not os.path.exists(model_path):
            print("模型" + station_id + ".h5丢失")
            return None
        loaded_model = load_model(model_path, compile=False)

        f_res = loaded_model.predict(X)
        f_res = f_res.flatten()
        f_res = np.maximum(f_res, 0)

        output_data = df.iloc[look_back:].reset_index(drop=True)
        output_data['预测发电功率'] = f_res
        output_data.loc[output_data["总辐射"] == 0, "预测发电功率"] = 0
        output_data['ID'] = station_id

        return output_data

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return None

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="2242787669a",
        port=3306,
        database="solar_db"
    )

def data_save(output_data):

    conn = get_db_connection()
    cursor = conn.cursor()

    # 遍历 DataFrame 并逐条插入或更新
    for _, row in output_data.iterrows():
        cursor.execute("""
            INSERT INTO solar_data (时间, 温度, 风速, 散射辐射, 直接辐射, 总辐射, 预测发电功率, ID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                温度 = VALUES(温度),
                风速 = VALUES(风速),
                散射辐射 = VALUES(散射辐射),
                直接辐射 = VALUES(直接辐射),
                总辐射 = VALUES(总辐射),
                预测发电功率 = VALUES(预测发电功率),
                ID = VALUES(ID)
        """, (
            row['时间'], row['温度'], row['风速'], row['散射辐射'],
            row['直接辐射'], row['总辐射'], row['预测发电功率'], row['ID']
        ))

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ID FROM station_info")
    stations = cursor.fetchall()
    cursor.close()
    conn.close()

    for station in stations:
        output_data=power_pre(station[0])
        if output_data is not None:
            data_save(output_data)