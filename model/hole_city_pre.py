import os
from datetime import datetime, timedelta
import pytz
import xarray as xr
import numpy as np
import pandas as pd
from pvlib.location import Location
from pvlib.pvsystem import PVSystem
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import pymysql


def data_clean(data):
    for i in range(len(data)):
        if i == 0 and (data[i] >= 2000 or data[i] < -1000):
            data[i] = 0
        if data[i] >= 2000 or data[i] < -1000:
            data[i] = data[i - 1]
    return data


def pvlib_pre_hole_city(
        weather_df: pd.DataFrame,
        electric_folder: str = 'electric',
        figures_folder: str = 'figures',
        metrics_save_path: str = 'metrics.csv',
        lat: float = 31,
        lon: float = 120,
        altitude: float = 5,
        capacity_kw: float = 1067179,  # 2273.6
        surface_tilt: float = 5,
        surface_azimuth: float = 200,
        tz: str = 'Asia/Shanghai',
        gamma: float = -0.001,
        eta_inv_nom: float = 0.7
):
    """
    使用 pvlib 模拟光伏发电，与实际观测值一起绘图并保存误差指标

    Parameters:
    - weather_df: 包含气象数据的 DataFrame，需包含时间、温度、风速和 GHI/DNI/DHI
    - electric_folder: 存放实际发电xls文件的文件夹路径
    - figures_folder: 保存绘图的文件夹
    - metrics_save_path: 保存误差指标表的路径
    - lat/lon: 地理坐标
    - altitude: 海拔
    - capacity_kw: 光伏装机容量（kW）
    - surface_tilt: 面板倾角（°）
    - surface_azimuth: 面板方位角（°）
    - tz: 时区
    - gamma: 参数，可选[0.01,0.001,0,-0.0001,-0.001,-0.002,-0.003,-0.004]
    - eta_inv_nom:  参数，可选0.7-1
    """

    weather_df = weather_df.copy()
    time = weather_df['时间'].astype(str)
    time = time.dropna()
    weather_df['时间'] = pd.to_datetime(weather_df['时间']).dt.tz_localize('Asia/Shanghai')
    weather_df = weather_df.set_index('时间').sort_index()

    # 准备气象数据
    weather = pd.DataFrame({
        'temp_air': weather_df['温度'],
        'wind_speed': weather_df['风速'],
        'ghi': weather_df['总辐射'],
        'dni': weather_df['直接辐射'],
        'dhi': weather_df['散射辐射']
    }, index=weather_df.index)
    # 构建 pvlib 模型
    location = Location(latitude=lat, longitude=lon, altitude=altitude, tz=tz)
    temperature_model_params = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    system = PVSystem(surface_tilt=surface_tilt,
                      surface_azimuth=surface_azimuth,
                      module_parameters={'pdc0': capacity_kw, 'gamma_pdc': gamma},
                      inverter_parameters={'pdc0': capacity_kw, 'eta_inv_nom': eta_inv_nom},
                      temperature_model_parameters=temperature_model_params)
    mc = ModelChain(system=system, location=location, aoi_model='physical',
                    spectral_model='no_loss', ac_model='pvwatts')
    mc.run_model(weather)
    predicted = mc.results.ac.fillna(0)
    return sum(predicted)


def data_prepare(data_folder):
    now = datetime.now(pytz.timezone('Asia/Shanghai'))
    current_month = now.month
    times_all = []
    temp_all = []
    wind_all = []
    swddif_all = []
    swddir_all = []
    swdd_all = []
    for filename in os.listdir(data_folder):
        if filename.endswith('.nc'):
            data_str = os.path.splitext(filename)[0].split('_')[-1]
            try:
                file_date = datetime.strptime(data_str, '%Y-%m-%d').date()
                file_date = file_date + timedelta(days=1)
            except ValueError:
                print(f'跳过日期不符合格式的文件：{filename}')
                continue
            file_month = file_date.month
            if file_month == current_month:
                # 读取nc文件
                file_path = os.path.join(data_folder, filename)
                df = xr.open_dataset(file_path)
                time_bytes = df['time'].values

                time_format = "%Y-%m-%d_%H:%M:%S"
                beijing_times = []
                start = 0
                end = 0
                for t in time_bytes:
                    # 解码字节字符串
                    time_str = t.decode('utf-8')
                    # 解析为 datetime 对象
                    utc_time = datetime.strptime(time_str, time_format)
                    # 转换为北京时间（UTC+8）
                    beijing_time = utc_time + timedelta(hours=8)
                    if beijing_time.date() < file_date:
                        start += 1
                    if beijing_time.date() == file_date:
                        end += 1
                        # 添加到结果列表
                        beijing_times.append(beijing_time)
                temp = np.round(df['T2'].values[start:start + end], 1)
                wind = np.round(df['WS10'].values[start:start + end], 1)
                swddif = np.round(df['SWDDIF'].values[start:start + end])
                swddir = np.round(df['SWDDIR'].values[start:start + end])
                SWDD = np.round(df['SWDDNI'].values[start:start + end]) + swddif
                times_all.extend(beijing_times)
                temp_all.extend(temp)
                wind_all.extend(wind)
                swddif_all.extend(swddif)
                swddir_all.extend(swddir)
                swdd_all.extend(SWDD)

    data = {"时间": times_all, "温度": temp_all, "风速": wind_all, "散射辐射": swddif_all, "直接辐射": swddir_all,
            "总辐射": swdd_all}
    data = pd.DataFrame(data)
    return data

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="2242787669a",
        port=3306,
        database="solar_db"
    )
if __name__ == '__main__':
    data_folder = '../data/new_weather_data'
    time=int(datetime.now().strftime("%Y%m"))
    data = data_prepare(data_folder)
    res = pvlib_pre_hole_city(data)*0.25
    conn = get_db_connection()
    cursor = conn.cursor()
    sql = """
    INSERT INTO hole_city (年月, 预测发电量)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE 预测发电量 = VALUES(预测发电量)
    """
    cursor.execute(sql, (time, res))
    conn.commit()
    conn.close()