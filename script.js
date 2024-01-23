const appsConfig = [
    {
        name: "Skywise",
        path: "apps/skywise",
        marketingPage: "apps/skywise/marketing/index.html",
        privacyPolicy: "apps/skywise/privacy/index.html",
        shortDescription: "apps/skywise/short-description.txt",
        iconImage: "apps/skywise/icon.png",
        color: "#dceff3"
    },
];

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
};

function showDetails(app, icon) {
    var icons = document.getElementsByClassName('app-icon');
    var detailCard = document.getElementById('detail-card');

    // Reset and hide close buttons for all icons
    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].querySelector('.close-btn').style.display = 'none';
    }

    // Mark the clicked icon as selected
    icon.classList.add('is-selected');
    var closeBtn = icon.querySelector('.close-btn');
    closeBtn.style.display = 'flex'; // Show close button for the selected icon

    // Fetch and display content for the selected app
    fetch(app.shortDescription)
        .then(response => response.text())
        .then(text => {
            detailCard.innerHTML = `<h3>${app.name} Details</h3><p>${text}</p>`;
            detailCard.innerHTML += `<a href='${app.marketingPage}' target='_blank'>Marketing Page</a><br>`;
            detailCard.innerHTML += `<a href='${app.privacyPolicy}' target='_blank'>Privacy Policy</a>`;

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

    for (var i = 0; i < icons.length; i++) {
        icons[i].classList.remove('is-selected');
        icons[i].style.transform = 'translateY(0%)';
        icons[i].style.width = '100px';
        icons[i].style.height = '100px';
        icons[i].querySelector('.close-btn').style.display = 'none';
    }

    detailCard.style.top = '70%';
    detailCard.style.opacity = '0';
    detailCard.style.transform = 'translateY(100%)';
}
