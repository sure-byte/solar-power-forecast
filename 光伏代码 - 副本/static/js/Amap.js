function initAmap(AMap, StationInfo, currentStationId) {
  const map = new AMap.Map('map', {
    center: [120.76249, 31.63811],
    zoom: 13
  });

  const markers = {};
  const normalIcon = new AMap.Icon({
    image: "/static/images/mark_b.png",  // 本地缓存
    size: new AMap.Size(19, 31),
    imageSize: new AMap.Size(19, 31)
  });

  const highlightIcon = new AMap.Icon({
    image: "/static/images/mark_r.png",  // 本地缓存
    size: new AMap.Size(28.5, 46.5),
    imageSize: new AMap.Size(28.5, 46.5)
  });

  const sharedInfoWindow = new AMap.InfoWindow({
    offset: new AMap.Pixel(10, -15),
    isCustom: true
  });

  StationInfo.forEach(station => {
    const isCurrent = station["ID"] === currentStationId;
    const marker = new AMap.Marker({
      position: [station["经度"], station["纬度"]],
      icon: isCurrent ? highlightIcon : normalIcon,
      map: map
    });

    const infoWindow = new AMap.InfoWindow({
      isCustom: true,
      content: `<div class="custom-window">
        <b>${station["ID"]}</b><br>
        装机容量：${station["装机容量"]} kW<br>
        角度：${station["角度"]} °
        </div>`,
      offset: new AMap.Pixel(10, -15)
    });

    marker.on('mouseover', () => infoWindow.open(map, marker.getPosition()));
    marker.on('mouseout', () => infoWindow.close());

    marker.on('click', () => {
      fetch('/set_station', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `station_id=${encodeURIComponent(station["ID"])}`
      }).then(response => {
        if (response.redirected) {
          window.location.href = response.url;
        } else {
          location.reload();
        }
      });
    });

    markers[station["ID"]] = marker;
  });

  addStationSearchControl(map, AMap, StationInfo, sharedInfoWindow);
}

function addStationSearchControl(map, AMap, StationInfo, sharedInfoWindow) {
  const controlDiv = document.createElement('div');
  controlDiv.style.cssText = `
    position: absolute; top: 10px; left: 10px; z-index: 999;
    background: white; padding: 8px; border: 1px solid #ccc;
    border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.3);
  `;

  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = '输入发电站 ID';
  input.style.cssText = `
    width: 180px; padding: 6px;
    margin-bottom: 4px; border-radius: 4px;
    border: 1px solid #aaa;
  `;
  input.setAttribute('list', 'stationList');

  const datalist = document.createElement('datalist');
  datalist.id = 'stationList';
  StationInfo.forEach(station => {
    const option = document.createElement('option');
    option.value = station["ID"];
    datalist.appendChild(option);
  });

  input.addEventListener('change', function () {
    const selectedID = input.value;
    const station = StationInfo.find(s => s.ID === selectedID);
    if (!station) return alert('找不到该电站');

    const pos = [station["经度"], station["纬度"]];
    sharedInfoWindow.setContent(`
      <div class="custom-window">
        <b>${station["ID"]}</b><br>
        装机容量：${station["装机容量"]} kW<br>
        角度：${station["角度"]} °
      </div>`);

    map.setZoomAndCenter(13, pos);
    sharedInfoWindow.open(map, pos);

    fetch('/set_station', {
      method: 'POST',
      headers: {'Content-Type': 'application/x-www-form-urlencoded'},
      body: `station_id=${encodeURIComponent(station["ID"])}`
    }).then(response => {
      if (response.redirected) {
        window.location.href = response.url;
      } else {
        location.reload();
      }
    });
  });

  controlDiv.appendChild(input);
  controlDiv.appendChild(datalist);
  map.getContainer().appendChild(controlDiv);
}
