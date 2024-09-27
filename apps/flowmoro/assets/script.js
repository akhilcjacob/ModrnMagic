fetch('descriptions.json')
  .then(response => response.json())
  .then(data => {
    // Update page title
    document.getElementById('app-title').textContent = data.title;

    const screenshots = data.screenshots;
    const textSections = data.textSections;
    const totalSections = screenshots.length;

    const screenshotElement = document.getElementById('screenshot');
    const sectionTitleElement = document.getElementById('section-title');
    const sectionOnelinerElement = document.getElementById('section-oneliner');

    document.getElementById('google-play-link').href = data.googlePlayLink;
    document.getElementById('app-store-link').href = data.appleStoreLink;

    const wipeElements = document.querySelectorAll('.wipe-transition');
    const textCardElement = document.getElementById('text-card');

    // Preload images
    screenshots.forEach(src => {
      const img = new Image();
      img.src = `screenshots/${src}`;
    });

    // Populate scroll sections
    const scrollSectionsContainer = document.querySelector('.scroll-sections');
    for (let i = 0; i < totalSections; i++) {
      const sectionDiv = document.createElement('div');
      sectionDiv.classList.add('section');
      scrollSectionsContainer.appendChild(sectionDiv);
    }

    // Set initial content
    let currentIndex = 0;
    updateContent(currentIndex);

    // Listen to scroll event
    window.addEventListener('scroll', () => {
      const scrollTop = window.scrollY;
      const viewportHeight = window.innerHeight;

      // Calculate current section index
      let newIndex = Math.floor(scrollTop / viewportHeight);
      newIndex = Math.min(newIndex, totalSections - 1);

      // Calculate scroll progress within the current section
      const sectionScrollTop = scrollTop - newIndex * viewportHeight;
      const sectionScrollProgress = sectionScrollTop / viewportHeight;

      // Update wipe progress
      const wipeProgress = sectionScrollProgress * 100;

      wipeElements.forEach(el => {
        el.style.setProperty('--wipe-progress', `${wipeProgress}%`);
      });

      // If index changed, update content
      if (newIndex !== currentIndex) {
        currentIndex = newIndex;
        updateContent(currentIndex);
      }
    });

    function updateContent(index) {
      // Update screenshot
      screenshotElement.src = `screenshots/${screenshots[index]}`;

      // Update text content
      sectionTitleElement.textContent = textSections[index].title;
      sectionOnelinerElement.textContent = textSections[index].oneliner;

      // Reset wipe progress to 0% for new content
      wipeElements.forEach(el => {
        el.style.setProperty('--wipe-progress', `0%`);
      });

      // Trigger text animation
      textCardElement.classList.remove('visible');
      void textCardElement.offsetWidth; // Trigger reflow to restart animation
      textCardElement.classList.add('visible');
    }

  })
  .catch(error => console.error('Error fetching data:', error));
