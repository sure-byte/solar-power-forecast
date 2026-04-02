window._AMapSecurityConfig = {
    securityJsCode: "9345ed8b34b777d9323581a4c058b914",
};

let map, marker;

function initInfoMap(longitude, latitude) {
    AMapLoader.load({
        key: "d4a6a4e5c22f41b3b2623c1a823013bd",
        version: "2.0",
    })
        .then((AMap) => {
            const lng = parseFloat(longitude) || 104.06;
            const lat = parseFloat(latitude) || 30.67;

            map = new AMap.Map("map-container", {
                zoom: 14,
                center: [lng, lat],
            });

            marker = new AMap.Marker({
                position: [lng, lat],
                draggable: true,
                map: map,
            });

            // 拖动标记同步经纬度
            marker.on("dragend", function (e) {
                const lng = e.lnglat.getLng().toFixed(6);
                const lat = e.lnglat.getLat().toFixed(6);
                updateInputs(lng, lat);
            });

            // 点击地图移动标记
            map.on("click", function (e) {
                const lng = e.lnglat.getLng().toFixed(6);
                const lat = e.lnglat.getLat().toFixed(6);
                marker.setPosition([lng, lat]);
                updateInputs(lng, lat);
            });

            const lngInput = document.getElementById("longitude");
            const latInput = document.getElementById("latitude");

            lngInput.addEventListener("input", () => syncMarker(lngInput, latInput));
            latInput.addEventListener("input", () => syncMarker(lngInput, latInput));
        })
        .catch((e) => {
            console.error("高德地图加载失败：", e);
        });
}

function updateInputs(lng, lat) {
    document.getElementById("longitude").value = lng;
    document.getElementById("latitude").value = lat;
}

function syncMarker(lngInput, latInput) {
    const lng = parseFloat(lngInput.value);
    const lat = parseFloat(latInput.value);
    if (!isNaN(lng) && !isNaN(lat)) {
        marker.setPosition([lng, lat]);
        map.setCenter([lng, lat]);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const toastElList = [].slice.call(document.querySelectorAll('.toast'))
    toastElList.forEach(function (toastEl) {
        new bootstrap.Toast(toastEl).show()
    })
});
