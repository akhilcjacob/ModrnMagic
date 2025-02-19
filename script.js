const appsConfig = [
    {
        name: "inboxhiiv",
        path: "apps/inboxhiiv",
        marketingImages: [

        ],
        appScreenshots: [
            "apps/inboxhiiv/screenshots/shot1.png"

        ],
        privacyPolicy: "apps/inboxhiiv/privacy/index.html",
        descriptionsJson: "apps/inboxhiiv/descriptions.json",
        iconImage: "apps/inboxhiiv/icon.png",
        color: "rgb(255,255,255	)",
        specificLink: "https://inboxhiiv.com"
    }, {
        name: "nookly",
        path: "apps/nookly",
        marketingImages: [
        ],
        appScreenshots: [
        ],
        privacyPolicy: "apps/nookly/privacy/index.html",
        descriptionsJson: "apps/nookly/descriptions.json",
        iconImage: "apps/nookly/icon.png",
        color: "rgb(173, 216, 230)", // Light blue color that complements dark blue
        specificLink: "https://nookly.co"
        
    },

    {
        name: "Flowmoro",
        path: "apps/flowmoro",
        marketingImages: [
            "apps/flowmoro/marketing/1.png",
            "apps/flowmoro/marketing/2.png",
            "apps/flowmoro/marketing/3.png",
            "apps/flowmoro/marketing/4.png"
        ],
        appScreenshots: [
            "apps/flowmoro/screenshots/1.png",
            "apps/flowmoro/screenshots/2.png",
            "apps/flowmoro/screenshots/3.png",
            "apps/flowmoro/screenshots/4.png"
        ],
        privacyPolicy: "apps/flowmoro/privacy/index.html",
        descriptionsJson: "apps/flowmoro/descriptions.json",
        iconImage: "apps/flowmoro/icon.png",
        color: "rgb(254,150,121	)",
        specificLink: "https://modrnmagic.app/apps/flowmoro/home"
    },
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
    {
        name: "Astro Defender",
        path: "apps/astrodefender",
        marketingImages: [
            "apps/astrodefender/marketing/1.png",
            "apps/astrodefender/marketing/2.png",
            "apps/astrodefender/marketing/3.png"
        ],
        appScreenshots: [
            "apps/astrodefender/screenshots/1.png",
            "apps/astrodefender/screenshots/2.png",
            "apps/astrodefender/screenshots/3.png",
            "apps/astrodefender/screenshots/4.png",
            "apps/astrodefender/screenshots/5.png",
            "apps/astrodefender/screenshots/6.png",
            "apps/astrodefender/screenshots/7.png",
            "apps/astrodefender/screenshots/8.png",
            "apps/astrodefender/screenshots/9.png",
            "apps/astrodefender/screenshots/10.png"
        ],
        privacyPolicy: "apps/astrodefender/privacy/index.html",
        descriptionsJson: "apps/astrodefender/descriptions.json",
        iconImage: "apps/astrodefender/icon.png",
        color: "rgb(1,5,28)"
    },

];

let mySwiper = null;


if (window.innerWidth > 768) { // pJS_desktop and pJS_mobile = my settings functions
    particlesJS.load('particles-js', 'particles.json', function () {
        console.log('callback - particles.js config loaded');
    });
} else {
    particlesJS.load('particles-js', 'particles-mobile.json', function () {
        console.log('callback - particles.js config loaded');
    });
}


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
    centerIcons();
};

function centerIcons() {
    const iconsContainer = document.querySelector('.icons-container');
    iconsContainer.style.position = 'absolute';
    iconsContainer.style.top = '50%';
    iconsContainer.style.transform = 'translateY(-50%)';
}




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

        if (window.innerWidth >= 768) {
            icons[i].style.width = ' 3.5rem'; // Shrinking size of the icon container
            icons[i].style.height = ' 3.5rem';
            icons[i].style.margin = '20px';
            icons[i].style.marginTop = '0.875rem';


        }
        else {
            icons[i].style.width = '50px'; // Shrinking size of the icon container
            icons[i].style.height = '50px';
            icons[i].style.margin = '10px';

            icons[i].style.marginTop = '0.5rem';

        }
        icons[i].querySelector('img').style.width = '50px'; // Shrinking size of the icon image
        icons[i].querySelector('img').style.height = '50px';

    }

    iconsContainer.style.justifyContent = 'start'; // This will remove 'center' alignment
    iconsContainer.style.flexDirection = 'row'
    // Mark the clicked icon as selected
    icon.classList.add('is-selected');
    var closeBtn = icon.querySelector('.close-btn');
    closeBtn.style.display = 'flex'; // Show close button for the selected icon


    // Fetch and display content for the selected app
    fetch(app.descriptionsJson)
        .then(response => response.json())
        .then(data => {
            const combinedImages = [...app.marketingImages, ...app.appScreenshots];
            console.log(data);
            detailCard.innerHTML = `
            <div class="mt-4 text-white">
                <img src="${app.iconImage}" alt="${app.name}" class="app-icon-detail">
                <h2 class="app-name">${app.name}</h2>
                <p class="app-oneliner pb-4">${data.oneliner}</p>
            </div>
            <div class="image-carousel">
                <div class="swiper">
                    <div class="swiper-wrapper">
                        <!-- Your slides go here -->
                    </div>
                    <div class="swiper-pagination"></div>
                    <div class="swiper-button-prev -4"></div>
                    <div class="swiper-button-next"></div>
                </div>
            </div>
            `;

            let storeButtonsHtml = '';
            let appSpecificButton = '';
            if (data.appleStoreLink) {
                storeButtonsHtml += `<div class="store-button apple-store-button" onclick="location.href='${data.appleStoreLink}'"><img alt='Get it on Apple App store' src='https://developer.apple.com/assets/elements/badges/download-on-the-app-store.svg'/></div>`;
            }

            if (data.googlePlayLink) {
                storeButtonsHtml += `<div class="store-button google-play-button" onclick="location.href='${data.googlePlayLink}'"><img alt='Get it on Google Play' src='https://play.google.com/intl/en_us/badges/static/images/badges/en_badge_web_generic.png'/></div>`;
            }
            if (app.specificLink) {
                appSpecificButton = `
                    <div class="homepage-link-container">
                        <a href="${app.specificLink}" class="homepage-link">Visit Homepage &gt;</a>
                    </div>`;
            }

            detailCard.innerHTML += `
                <div class="store-buttons-container">
                    ${storeButtonsHtml}
                </div>
                ${appSpecificButton}

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
            // adjustDetailCardPosition();
            const iconsContainer = document.querySelector('.icons-container');
            iconsContainer.style.position = 'static';
            iconsContainer.style.transform = 'translateY(0)';
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
    detailCard.style.opacity = '0';
    detailCard.style.transform = 'translateY(100%)';

    if (window.innerWidth <= 768) {
        var iconsContainer = document.querySelector('.icons-container');
        if (iconsContainer) {
            iconsContainer.style.flexDirection = 'column';
        }
    }

    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');

        icons[i].style.transform = 'translateY(0%)';
        icons[i].style.width = '100px';
        icons[i].style.height = '100px';
        icons[i].style.margin = '20px';
        icons[i].querySelector('img').style.width = '80px'; // Resetting icon image size to original
        icons[i].querySelector('img').style.height = '80px';
        icons[i].querySelector('.close-btn').style.display = 'none';
    }

    centerIcons();
}


