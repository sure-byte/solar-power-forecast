// 初始化地图
var oms_map = L.map('map', {
    center: [31.63811, 120.76249],
    zoom: 13,
    zoomControl: false
});

// 定义 OSM 图层
var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
});

// 定义高德图层（使用插件）
var gaodeLayer = L.tileLayer.chinaProvider('GaoDe.Normal.Map', {
    attribution: '© 高德地图'
});

// 默认添加一个图层，例如 OSM
osmLayer.addTo(oms_map);

// 图层切换控件（可选）
var baseLayers = {
    "OpenStreetMap": osmLayer,
    "高德地图": gaodeLayer
};
L.control.layers(baseLayers).addTo(oms_map);

// 自定义图标
var normalIcon = L.icon({
    iconUrl: '/static/images/marker-b.png',
    iconSize: [30, 30],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34]
});

var highlightIcon = L.icon({
    iconUrl: '/static/images/marker-r.png',
    iconSize: [50, 50],
    iconAnchor: [15, 50],
    popupAnchor: [1, -34]
});

const markers = {};

// 添加用户标记
UserInfo.forEach(user => {
    const isCurrent = user["光伏用户编号"] === currentUserId;
    const marker = L.marker(
        [user["纬度"], user["经度"]],
        {icon: isCurrent ? highlightIcon : normalIcon}
    ).addTo(oms_map).bindPopup(`
    <b>${user["光伏用户编号"]}</b><br>
    装机容量：${user["装机容量"]} kW<br>
    综合倍率：${user["综合倍率"]}
  `, {closeButton: false});

    marker.on('mouseover', function () {
        this.openPopup();
    });
    marker.on('mouseout', function () {
        this.closePopup();
    });

    let lastClickTime = 0;
    const doubleTapThreshold = 300;
    marker.on('click', function () {
        const now = Date.now();
        if (now - lastClickTime <= doubleTapThreshold) {
            handleDoubleClick();
            lastClickTime = 0;
        } else {
            lastClickTime = now;
        }
    });
    marker.on('dblclick', function () {
        handleDoubleClick();
    });

    function handleDoubleClick() {
        fetch('/set_user', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: `user_id=${encodeURIComponent(user["光伏用户编号"])}`
        }).then(response => {
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                location.reload();
            }
        });
    }

    markers[user["光伏用户编号"]] = marker;
});

// 添加用户切换控件
var MultiRecenterControl = L.Control.extend({
    onAdd: function (map) {
        var container = L.DomUtil.create('div', 'custom-control');
        UserInfo.forEach(user => {
            var btn = document.createElement('button');
            btn.innerText = user["光伏用户编号"];
            btn.onclick = function () {
                map.setView([user["纬度"], user["经度"]], 14);
                markers[user["光伏用户编号"]].openPopup();
            };
            container.appendChild(btn);
        });
        return container;
    },
    onRemove: function (map) {
    }
});
oms_map.addControl(new MultiRecenterControl({position: 'topleft'}));
