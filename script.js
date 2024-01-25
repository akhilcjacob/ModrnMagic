const appsConfig = [
    {
        name: "SkyWise",
        path: "apps/skywise",
        marketingImages: [
            "apps/skywise/marketing/1.jpg",
            "apps/skywise/marketing/2.jpg",
            "apps/skywise/marketing/3.jpg",
            "apps/skywise/marketing/4.jpg"
        ],
        appScreenshots: [
            "apps/skywise/screenshots/Photo Nov 8.png",
            "apps/skywise/screenshots/Screenshot Nov 8.png"
        ],
        privacyPolicy: "apps/skywise/privacy/index.html",
        descriptionsJson: "apps/skywise/descriptions.json",
        iconImage: "apps/skywise/icon.png",
        color: "#dceff3"
    },
];
let mySwiper = null;

particlesJS.load('particles-js', 'particles.json', function () {
    console.log('callback - particles.js config loaded');
});

window.onload = function () {
    const iconsContainer = document.querySelector('.icons-container');
    appsConfig.forEach(app => {
        const icon = document.createElement('div');
        icon.className = 'app-icon';
        icon.style.background = app.color;
        icon.onclick = () => showDetails(app);


        const iconImg = new Image();
        iconImg.src = app.iconImage;
        iconImg.alt = app.name;
        icon.appendChild(iconImg);

        icon.onclick = () => showDetails(app, icon);


        const closeButton = document.createElement('div');
        closeButton.className = 'close-btn hidden';
        closeButton.onclick = (event) => closeDetails(event, closeButton);
        icon.appendChild(closeButton);

        iconsContainer.appendChild(icon);
    });
    iconsContainer.style.top = '0px'; // Set initial top position
};


function showDetails(app, icon) {
    var icons = document.getElementsByClassName('app-icon');
    var detailCard = document.getElementById('detail-card');
    var iconsContainer = document.querySelector('.icons-container');
    iconsContainer.style.justifyContent = 'flex-start'; // This will align icons to the start

    detailCard.style.display = 'block';

    // Reset and hide close buttons for all icons
    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].querySelector('.close-btn').style.display = 'none';
        icons[i].style.width = '60px'; // Shrinking size of the icon container
        icons[i].style.height = '60px';
        icons[i].querySelector('img').style.width = '50px'; // Shrinking size of the icon image
        icons[i].querySelector('img').style.height = '50px';
    }

    iconsContainer.style.justifyContent = 'start'; // This will remove 'center' alignment

    // Mark the clicked icon as selected
    icon.classList.add('is-selected');
    var closeBtn = icon.querySelector('.close-btn');
    closeBtn.style.display = 'flex'; // Show close button for the selected icon


    // Fetch and display content for the selected app
    fetch(app.descriptionsJson)
        .then(response => response.json())
        .then(data => {
            const combinedImages = [...app.marketingImages, ...app.appScreenshots];

            detailCard.innerHTML = `
            <div class="mt-8 text-white">
                <img src="${app.iconImage}" alt="${app.name}" class="app-icon-detail">
                <h2 class="app-name">${app.name}</h2>
                <p class="app-oneliner">${data.oneliner}</p>
            </div>
            <div class="image-carousel">
                <div class="swiper">
                    <div class="swiper-wrapper">
                        <!-- Your slides go here -->
                    </div>
                    <div class="swiper-pagination"></div>
                    <div class="swiper-button-prev"></div>
                    <div class="swiper-button-next"></div>
                </div>
                <p class="app-description">${data.description}</p>
            </div>
            `;


            // Destroy previous Swiper instance if it exists
            if (mySwiper) {
                mySwiper.destroy();
                mySwiper = null;
            }


            // Initialize carousel here 
            const swiperWrapper = document.querySelector('.swiper-wrapper');
            swiperWrapper.innerHTML = ''; 

            combinedImages.forEach(image => {
                console.log(image);
                const slide = document.createElement('div');
                slide.className = 'swiper-slide';
                slide.innerHTML = `<img src="${image}" alt="Image" class="carousel-image">`;
                swiperWrapper.appendChild(slide);
            });
            setTimeout(() => {
                mySwiper = new Swiper('.swiper', {
                    // Swiper parameters
                    loop: true,
                    pagination: {
                        el: '.swiper-pagination',
                    },
                    navigation: {
                        nextEl: '.swiper-button-next',
                        prevEl: '.swiper-button-prev',
                    },
                });
            }, 0);

            // Make sure the detail card is visible
            detailCard.style.opacity = '1';
            detailCard.style.transform = 'translateY(0)';
            adjustDetailCardPosition();

        })
        .catch(error => {
            console.error('Error fetching app details:', error);
            // Handle the error or display a default message
            detailCard.innerHTML = `<h3>Error Loading Details</h3><p>Could not load details for ${app.name}.</p>`;
            detailCard.style.opacity = '1';
            detailCard.style.transform = 'translateY(0)';
        });
}


function adjustDetailCardPosition() {
    const iconsContainer = document.querySelector('.icons-container');
    const detailCard = document.getElementById('detail-card');
    const iconsContainerHeight = iconsContainer.offsetHeight; // Get the height of the icons container
    detailCard.style.top = `${iconsContainerHeight}px`; // Position the detail card just below the icons container
}


function closeDetails(event, btn) {
    event.stopPropagation();

    var icons = document.getElementsByClassName('app-icon');


    var detailCard = document.getElementById('detail-card');
    detailCard.innerHTML = '';
    detailCard.style.display = 'none';

    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].style.transform = 'translateY(0%)';
        icons[i].style.width = '100px';
        icons[i].style.height = '100px';
        icons[i].querySelector('img').style.width = '80px'; // Resetting icon image size to original
        icons[i].querySelector('img').style.height = '80px';
        icons[i].querySelector('.close-btn').style.display = 'none';
    }

    detailCard.style.top = '0%';
    detailCard.style.opacity = '0';
    detailCard.style.transform = 'translateY(100%)';
    // iconsContainer.style.top = '0px'; // Reset to original position

}

