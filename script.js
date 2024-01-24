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

function getPngImagesFromFolder(){
    // TODO FUNCTION TO FETCH THE IMAGES
}

function showDetails(app, icon) {
    var icons = document.getElementsByClassName('app-icon');
    var detailCard = document.getElementById('detail-card');
    var iconsContainer = document.querySelector('.icons-container');


    // Reset and hide close buttons for all icons
    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].querySelector('.close-btn').style.display = 'none';
        icons[i].style.width = '60px'; // Shrinking size of the icon container
        icons[i].style.height = '60px';
        icons[i].querySelector('img').style.width = '50px'; // Shrinking size of the icon image
        icons[i].querySelector('img').style.height = '50px';
    }

    // Mark the clicked icon as selected
    icon.classList.add('is-selected');
    var closeBtn = icon.querySelector('.close-btn');
    closeBtn.style.display = 'flex'; // Show close button for the selected icon

    var iconsContainer = document.querySelector('.icons-container');
    var desiredOffset = 30; // The desired distance from the top

    // Move the icons container up, leaving 10px from the top
    iconsContainer.style.top = `-${iconsContainer.offsetTop - desiredOffset}px`;


    // Fetch and display content for the selected app
    fetch(app.descriptionsJson)
        .then(response => response.json())
        .then(data => {
            const marketingImages = getPngImagesFromFolder(app.marketingImages);
            const appScreenshots = getPngImagesFromFolder(app.appScreenshots);
            const combinedImages = [...marketingImages, ...appScreenshots];

            detailCard.innerHTML = `
                <div class="detail-top pt-7 text-white" >
                    <img src="${app.iconImage}" alt="${app.name}" class="app-icon-detail">
                    <h2 class="app-name">${app.name}</h2>
                    <p class="app-oneliner">${data.oneliner}</p>
                </div>
                <div class="detail-bottom">
                    <div class="image-carousel">
                    // TODO: Add carousel
                    </div>
                    <p class="app-description">${data.description}</p>
                </div>
            `;

            // Initialize carousel here (if using a plugin)
            // e.g., $('.image-carousel').initCarouselPlugin();

            // Make sure the detail card is visible
            detailCard.style.opacity = '1';
            detailCard.style.transform = 'translateY(0)';
        })
        .catch(error => {
            console.error('Error fetching app details:', error);
            // Handle the error or display a default message
            detailCard.innerHTML = `<h3>Error Loading Details</h3><p>Could not load details for ${app.name}.</p>`;
            detailCard.style.opacity = '1';
            detailCard.style.transform = 'translateY(0)';
        });
}



function closeDetails(event, btn) {
    event.stopPropagation();

    var icons = document.getElementsByClassName('app-icon');
    var detailCard = document.getElementById('detail-card');
    var iconsContainer = document.querySelector('.icons-container'); // Re-query the icons container
    detailCard.innerHTML = '';

    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].style.transform = 'translateY(0%)';
        icons[i].style.width = '100px';
        icons[i].style.height = '100px';
        icons[i].querySelector('img').style.width = '80px'; // Resetting icon image size to original
        icons[i].querySelector('img').style.height = '80px';
        icons[i].querySelector('.close-btn').style.display = 'none';
    }

    detailCard.style.top = '70%';
    detailCard.style.opacity = '0';
    detailCard.style.transform = 'translateY(100%)';
    iconsContainer.style.top = '0px'; // Reset to original position

}

