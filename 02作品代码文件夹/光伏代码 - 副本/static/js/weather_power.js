//动画控制器
document.addEventListener("DOMContentLoaded", function () {
    // ---- Lottie 动画部分 ----
    const container = document.getElementById("temperature-icon");

    let animationPath, segment;
    if (temp < 15) {
        animationPath = "/static/images/temperature_cold.json";
        segment = [88, 128];
    } else {
        animationPath = "/static/images/temperature_hot.json";
        segment = [102, 194];
    }
    console.log(animationPath);
    const anim = lottie.loadAnimation({
        container: container,
        renderer: 'svg',
        loop: true,
        autoplay: false,
        path: animationPath
    });

    anim.setSpeed(1);

    anim.addEventListener('DOMLoaded', function () {
        anim.playSegments(segment, true);
    });

    anim.addEventListener('data_ready', function () {
        anim.play();
    });
});

//天气图
document.addEventListener("DOMContentLoaded", function () {
    const labels = Data.map(item => item.时间);
    const temps = Data.map(item => item.温度.toFixed(2));
    const wind = Data.map(item => item.风速.toFixed(2));
    const irradiance = Data.map(item => item.总辐射.toFixed(2));

    const itemsPerPage = 12 * 4 + 1; // 96条数据
    let currentPage = 0;
    const totalPages = Math.ceil(Data.length / itemsPerPage);

    const { prevBtn, nextBtn, pageInfo } = getPaginationControls();

    const charts = {
        temp: createSingleChart(document.getElementById("tempChart").getContext("2d"), "温度 (°C)", temps, "#ff5733", { min: 0, max: 20 }),
        wind: createSingleChart(document.getElementById("windChart").getContext("2d"), "风速 (m/s)", wind, "#8c8c8c", { min: 0, max: 3 }),
        irradiance: createSingleChart(document.getElementById("irradianceChart").getContext("2d"), "辐照强度 (W/m²)", irradiance, "#ede453", { min: 0, max: 600 }),
    };

    // 初始更新
    updateAllCharts();

    // 分页按钮点击事件
    prevBtn.addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            updateAllCharts();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentPage < totalPages - 1) {
            currentPage++;
            updateAllCharts();
        }
    });

    function updateAllCharts() {
        updateChart(charts.temp, temps);
        updateChart(charts.wind, wind);
        updateChart(charts.irradiance, irradiance);
        updatePaginationInfo();
    }

    function updateChart(chart, dataArray) {
        const start = currentPage * (itemsPerPage);
        const end = Math.min(start + itemsPerPage, labels.length);

        chart.data.labels = labels.slice(start, end);
        chart.data.datasets[0].data = dataArray.slice(start, end);
        chart.update();
    }

    function updatePaginationInfo() {
        if (pageInfo) {
            pageInfo.textContent = `${currentPage + 1} / ${totalPages}`;
        }
        prevBtn.classList.toggle('disabled', currentPage === 0);
        nextBtn.classList.toggle('disabled', currentPage === totalPages - 1);
    }

    function createSingleChart(ctx, label, data, color, range) {
        return new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels.slice(0, itemsPerPage),
                datasets: [{
                    label: label,
                    data: data.slice(0, itemsPerPage),
                    borderColor: color,
                    backgroundColor: color + '33',
                    tension: 0.3,
                    fill: 'start',
                    pointRadius: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            callback: function (value, index) {
                                const timeStr = this.getLabelForValue(value);
                                const date = new Date(timeStr.replace(/-/g, '/'));
                                const hours = date.getHours().toString().padStart(2, '0');
                                const minutes = date.getMinutes().toString().padStart(2, '0');
                                const seconds = date.getSeconds().toString().padStart(2, '0');

                                if (hours === "06" && minutes === "00" && seconds === "00") {
                                    return `${date.getMonth() + 1}月${date.getDate()}日`;
                                }
                                if (minutes === "00" && seconds === "00") {
                                    return `${hours}:00`;
                                }
                                return "";
                            },
                            autoSkip: false,
                            maxRotation: 0,
                            minRotation: 0
                        }
                    },
                    y: {
                        grid: { display: false },
                        beginAtZero: false,
                        suggestedMin: range.min,
                        suggestedMax: range.max
                    }
                }
            }
        });
    }

    function getPaginationControls() {
        return {
            prevBtn: document.querySelector('.pagination-prev'),
            nextBtn: document.querySelector('.pagination-next'),
            pageInfo: document.querySelector('.page-info')
        };
    }

    // 图表切换按钮逻辑
    window.WeatherChart = function (type, button) {
        document.querySelectorAll('.weather-chart').forEach(canvas => {
            canvas.classList.add('hidden');
        });
        document.getElementById(type + "Chart").classList.remove('hidden');

        document.querySelectorAll('.chart-btn.weather').forEach(btn => {
            btn.classList.remove('active');
        });
        button.classList.add('active');
    };
});

//电量图
document.addEventListener("DOMContentLoaded", function () {
    const itemsPerPage = 12 * 4 + 1; // 24小时，15分钟间隔
    let currentPage = 0;
    const totalPages = Math.ceil(Data.length / itemsPerPage);

    const prevBtn = document.querySelector('.pagination-prev-power');
    const nextBtn = document.querySelector('.pagination-next-power');
    const pageInfo = document.querySelector('.page-info-power');

    function updatePaginationControls() {
        pageInfo.textContent = `${currentPage + 1} / ${totalPages}`;
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage === totalPages - 1;
    }

    function getPagedData(page) {
        const start = page * (itemsPerPage);
        const end = start + itemsPerPage;
        const pageData = Data.slice(start, end);
        return {
            labels: pageData.map(item => item.时间),
            predicted: pageData.map(item => item.预测发电功率)
        };
    }

    let power24ChartInstance = null;

    function drawPower24Chart({ canvasId, labels, predictedData }) {
        const ctx = document.getElementById(canvasId).getContext("2d");

        // 如果图表已存在，更新数据
        if (power24ChartInstance) {
            power24ChartInstance.data.labels = labels;
            power24ChartInstance.data.datasets[0].data = predictedData;
            power24ChartInstance.update();
            return;
        }

        // 初始化图表
        power24ChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: "预测发电功率 (kW)",
                    data: predictedData,
                    borderColor: "#f1c40f",
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: 0,
                            minRotation: 0,
                            autoSkip: false,
                            callback: function (value, index, ticks) {
                                const timeStr = this.getLabelForValue(value);
                                const date = new Date(timeStr.replace(/-/g, '/'));
                                const hours = date.getHours().toString().padStart(2, '0');
                                const minutes = date.getMinutes().toString().padStart(2, '0');
                                const seconds = date.getSeconds().toString().padStart(2, '0');
                                if (hours === "06" && minutes === "00" && seconds === "00") {
                                    return `${date.getMonth() + 1}月${date.getDate()}日`;
                                } else if (minutes === "00" && seconds === "00") {
                                    return `${hours}:00`;
                                }
                                return "";
                            }
                        },
                        grid: { display: false }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { display: false }
                    }
                }
            }
        });
    }

    // 初始图表渲染
    const firstPage = getPagedData(currentPage);
    drawPower24Chart({
        canvasId: "power24Chart",
        labels: firstPage.labels,
        predictedData: firstPage.predicted
    });
    updatePaginationControls();

    // 绑定事件监听器
    prevBtn.addEventListener("click", () => {
        if (currentPage > 0) {
            currentPage--;
            const pageData = getPagedData(currentPage);
            drawPower24Chart({
                canvasId: "power24Chart",
                labels: pageData.labels,
                predictedData: pageData.predicted
            });
            updatePaginationControls();
        }
    });

    nextBtn.addEventListener("click", () => {
        if (currentPage < totalPages - 1) {
            currentPage++;
            const pageData = getPagedData(currentPage);
            drawPower24Chart({
                canvasId: "power24Chart",
                labels: pageData.labels,
                predictedData: pageData.predicted
            });
            updatePaginationControls();
        }
    });

    function drawDay7PowerChart({canvasId, labels, showActual = false, actualData = [], predictedData = [], showLegend = true}) {
        const ctx = document.getElementById(canvasId).getContext("2d");

        const datasets = [];

        if (showActual) {
            datasets.push({
                label: "实际总发电量 (kWh)",
                data: actualData,
                backgroundColor: "#3498db"
            });
        }

        datasets.push({
            label: "预测总发电量 (kWh)",
            data: predictedData,
            backgroundColor: "#f1c40f"
        });

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: showLegend,
                        position: "top"
                    }
                },
                scales: {
                    x: {
                        grid: {display: false},
                        stacked: false
                    },
                    y: {
                        beginAtZero: true,
                        grid: {display: true}
                    }
                }
            }
        });
    }

    let startIndex = 0;
    let endIndex = Data.length - 1;

    // 找到第一个完整日期（时间为 00:00:00）
    for (let i = 0; i < Data.length; i++) {
        if (Data[i].时间.endsWith("00:00:00")) {
            startIndex = i;
            break;
        }
    }

    // 找到最后一个完整日期（时间为 00:00:00）的位置
    for (let i = Data.length - 1; i >= 0; i--) {
        if (Data[i].时间.endsWith("00:00:00")) {
            endIndex = i;  // 包括最后一个完整日期的数据
            break;
        }
    }

    // 截取从第一个完整日期到下一个完整日期之前的数据
    const lastDataRange = Data.slice(startIndex, endIndex);

    // 计算每个日期的预测发电量总和
    let dateSums = {};
    lastDataRange.forEach(item => {
        const date = item.时间.slice(0, 10);  // 提取日期部分
        if (!dateSums[date]) {
            dateSums[date] = 0;
        }
        dateSums[date] += item.预测发电功率 * 0.25 || 0;
    });

    const labels7 = Object.keys(dateSums);
    const forecastTotals = labels7.map(date => dateSums[date]);
    drawDay7PowerChart({
        canvasId: "power7dChart",
        labels: labels7,
        showActual: false,
        predictedData: forecastTotals,
        showLegend: false
    });
});

document.addEventListener('DOMContentLoaded', function () {
    const toastElList = [].slice.call(document.querySelectorAll('.toast'))
    toastElList.forEach(function (toastEl) {
        new bootstrap.Toast(toastEl).show()
    })
});

//图表控制器
function WeatherChart(type, button) {
    const charts = ['temp', 'wind', 'irradiance'];
    charts.forEach(id => {
        const el = document.getElementById(id + "Chart");
        if (el) el.classList.add("hidden");
    });
    document.getElementById(type + "Chart").classList.remove("hidden");
    const buttons = document.querySelectorAll('.weather');
    buttons.forEach(btn => btn.classList.remove('active'));
    button.classList.add('active');
}

function PowerChart(type, button) {
    const charts = ['power24', 'power7d'];
    charts.forEach(id => {
        const el = document.getElementById(id + "Chart");
        if (el) el.classList.add("hidden");
    });

    // 显示目标图表
    document.getElementById(type + "Chart").classList.remove("hidden");

    // 切换按钮样式
    const buttons = document.querySelectorAll('.power');
    buttons.forEach(btn => btn.classList.remove('active'));
    button.classList.add('active');

    // 控制分页按钮和页码显示
    const paginationPrev = document.querySelector('.pagination-prev-power');
    const paginationNext = document.querySelector('.pagination-next-power');
    const pageInfo = document.querySelector('.page-info-power');

    const showPagination = (type === 'power24');

    const disabled = !showPagination;

    [paginationPrev, paginationNext].forEach(btn => {
        btn.style.color = disabled ? "#ffffff" : "#666";
        btn.style.pointerEvents = disabled ? "none" : "auto";
    });
    pageInfo.style.color = disabled ? "#ffffff" : "#666";

}

(function () {
  let dischargeChartInst = null;
  let optChartInst = null;

  function destroyIfExist(chartInst) {
    if (chartInst && typeof chartInst.destroy === 'function') {
      chartInst.destroy();
    }
  }

  // 用新的 results 重绘两张图
  function rebuildStorageCharts(results) {
    // 安全清空旧图
    destroyIfExist(dischargeChartInst);
    destroyIfExist(optChartInst);

    // 读数据（与原 IIFE 的 buildCharts 保持一致）
    const sorted = (results || []).slice().sort((a, b) => String(a['时间']).localeCompare(String(b['时间'])));
    const labels = sorted.map(d => String(d['时间']));

    const roundSmall = (x) => {
      const v = Number(x) || 0;
      return Math.abs(v) < 1e-8 ? 0 : v;
    };
    const discharge = sorted.map(d => roundSmall(d['实际放电功率']));
    const before    = sorted.map(d => roundSmall((Number(d['负荷']) || 0) - (Number(d['光伏']) || 0)));
    const after     = sorted.map((d, i) => roundSmall(before[i] - (Number(d['实际放电功率']) || 0)));

    const dischargeCanvas = document.getElementById('dischargeChart');
    const optCanvas = document.getElementById('optChart');
    const empty1 = document.getElementById('dischargeEmpty');
    const empty2 = document.getElementById('optEmpty');

    const hasData = Array.isArray(results) && results.length > 0;

    // 空态切换
    if (!hasData) {
      if (dischargeCanvas) dischargeCanvas.classList.add('d-none');
      if (optCanvas) optCanvas.classList.add('d-none');
      if (empty1) empty1.classList.remove('d-none');
      if (empty2) empty2.classList.remove('d-none');
      return;
    } else {
      if (dischargeCanvas) dischargeCanvas.classList.remove('d-none');
      if (optCanvas) optCanvas.classList.remove('d-none');
      if (empty1) empty1.classList.add('d-none');
      if (empty2) empty2.classList.add('d-none');
    }

    // 1) 实际放电功率
    if (dischargeCanvas) {
      dischargeChartInst = new Chart(dischargeCanvas.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: '实际放电功率 (kW)',
            data: discharge,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {mode: 'index', intersect: false},
          plugins: {legend: {display: true}},
          scales: {
            x: {ticks: {maxTicksLimit: 12}},
            y: {title: {display: true, text: 'kW'}, beginAtZero: false}
          }
        }
      });
    }

    // 2) 优化前 vs 优化后
    if (optCanvas) {
      optChartInst = new Chart(optCanvas.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: '优化前(kW)', data: before, borderWidth: 2, pointRadius: 0, tension: 0.2 },
            { label: '优化后(kW)', data: after,  borderWidth: 2, pointRadius: 0, borderDash: [6,4], tension: 0.2 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {mode: 'index', intersect: false},
          plugins: {legend: {display: true}},
          scales: {
            x: {ticks: {maxTicksLimit: 12}},
            y: {title: {display: true, text: 'kW'}, beginAtZero: false}
          }
        }
      });
    }
  }

  // 更新“文字指标”
  function updateStorageNumbers({p_max, q_max, raw_cost, opted_cost, save_cost}) {
    const set = (id, v, digits=2) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (Number(v) || 0).toFixed(digits);
    };
    set('pmax-text', p_max);
    set('qmax-text', q_max);
    set('rawcost-text', raw_cost, 2);
    set('optcost-text', opted_cost, 2);
    set('savecost-text', save_cost, 2);
  }
  async function fetchAndRefresh() {
    const selA = document.getElementById('scaleASelect');
    const selB = document.getElementById('scaleBSelect');
    if (!selA || !selB) return;

    const scale_a = selA.value;
    const scale_b = selB.value;

    const resp = await fetch(`/storage_section?scale_a=${encodeURIComponent(scale_a)}&scale_b=${encodeURIComponent(scale_b)}`);
    if (!resp.ok) throw new Error('请求失败');
    const data = await resp.json();

    updateStorageNumbers(data);
    rebuildStorageCharts(data.results);
  }

    // === 改：监听下拉框变化，自动刷新 ===
    function bindSelectAutoRefresh() {
        const selA = document.getElementById('scaleASelect');
        const selB = document.getElementById('scaleBSelect');
        if (!selA || !selB) return;

        const onChange = () => {
            fetchAndRefresh().catch(e => console.error('局部更新失败：', e));
        };
        selA.addEventListener('change', onChange);
        selB.addEventListener('change', onChange);
    }

    // === 新增：首次进入页面自动刷新一次（解决“第一次不显示”）===
    function initialRefreshWhenReady() {
        // 1) 立即尝试一次
        fetchAndRefresh().catch(e => console.warn('初次刷新失败（稍后重试）：', e));

        // 2) 如果第四页一开始是隐藏（宽度为0），可见时再 resize/重绘
        const section = document.getElementById('storage-section');
        if (!section) return;

        // 用 IntersectionObserver 监听可见
        const io = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                // 容器可见后，强制 Chart.js 重新计算尺寸
                try {
                    if (dischargeChartInst && typeof dischargeChartInst.resize === 'function') dischargeChartInst.resize();
                    if (optChartInst && typeof optChartInst.resize === 'function') optChartInst.resize();
                } catch (e) { /* 忽略 */
                }
            });
        }, {threshold: 0.2});
        io.observe(section);

        // 用 ResizeObserver 兜底，当容器从 0 宽变为有宽度时，触发一次 resize
        if (typeof ResizeObserver !== 'undefined') {
            const ro = new ResizeObserver(() => {
                try {
                    if (dischargeChartInst && typeof dischargeChartInst.resize === 'function') dischargeChartInst.resize();
                    if (optChartInst && typeof optChartInst.resize === 'function') optChartInst.resize();
                } catch (e) { /* 忽略 */
                }
            });
            ro.observe(section);
        }
    }

    // 页面就绪后：绑定监听 + 首次刷新
    function boot() {
        bindSelectAutoRefresh();
        initialRefreshWhenReady();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
