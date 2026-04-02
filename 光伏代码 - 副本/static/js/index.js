// 时间轴轮播功能
let currentIndex = 0;
const images = document.querySelectorAll('.carousel-image');
const textItems = document.querySelectorAll('.carousel-text-item');
const buttons = document.querySelectorAll('.timeline-button');

function changeSlide() {
    images.forEach(img => img.style.display = 'none');
    textItems.forEach(text => {
        text.style.display = 'none';
        text.style.opacity = 0;
    });

    images[currentIndex].style.display = 'block';
    const currentText = textItems[currentIndex];
    currentText.style.display = 'block';
    currentText.style.animation = 'fadeInUp 1s ease forwards';

    buttons.forEach(button => button.classList.remove('active'));
    buttons[currentIndex].classList.add('active');

    currentIndex = (currentIndex + 1) % images.length;
}

changeSlide();
let slideInterval = setInterval(changeSlide, 5000);

buttons.forEach(button => {
    button.addEventListener('click', (e) => {
        clearInterval(slideInterval);
        currentIndex = parseInt(button.getAttribute('data-index'));
        changeSlide();
        slideInterval = setInterval(changeSlide, 5000);
    });
});

// 滚动触发动画功能
function revealOnScroll() {
    const sections = document.querySelectorAll('.forecast-system-section');

    sections.forEach(section => {
        const sectionTop = section.getBoundingClientRect().top;
        const windowHeight = window.innerHeight;

        if (sectionTop < windowHeight - 100) {
            section.classList.add('reveal');
        }
    });
}

// 初始检查
window.addEventListener('scroll', revealOnScroll);
window.addEventListener('load', revealOnScroll);

document.addEventListener('DOMContentLoaded', function () {
    const toastElList = [].slice.call(document.querySelectorAll('.toast'))
    toastElList.forEach(function (toastEl) {
        new bootstrap.Toast(toastEl).show()
    })
});

document.addEventListener('DOMContentLoaded', function() {
    // 从HTML元素获取数据
    const powerDataElement = document.getElementById('power-data');
    const records = JSON.parse(powerDataElement.dataset.records);

    // 处理数据格式
    const processedRecords = records.map(r => ({
        date: `${Math.floor(r['年月']/100)}年${r['年月']%100}月`,
        value: r['预测发电量'] / 10000.0
    }));

    let currentIndex = processedRecords.length - 1;

    // 初始化显示
    updateDisplay();

    // 事件监听
    document.querySelector('.left-arrow').addEventListener('click', function() {
        if (currentIndex > 0) {
            currentIndex--;
            updateDisplay();
        }
    });

    document.querySelector('.right-arrow').addEventListener('click', function() {
        if (currentIndex < processedRecords.length - 1) {
            currentIndex++;
            updateDisplay();
        }
    });

    function updateDisplay() {
        const currentRecord = processedRecords[currentIndex];
        document.getElementById('record-date').textContent = currentRecord.date;
        document.getElementById('record-value').textContent =
            currentRecord.value.toFixed(2) + '万千瓦时';
    }
});