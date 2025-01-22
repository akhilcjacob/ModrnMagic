(function() {
    // Initialize EmailJS
    emailjs.init("vS3CR-R0Bjl5BLllJ");

    // Form submission handler
    document.getElementById('contact-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Show loading state
        const submitButton = this.querySelector('button[type="submit"]');
        const originalText = submitButton.innerHTML;
        submitButton.disabled = true;
        submitButton.innerHTML = `
            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span class="ml-2">Sending...</span>
        `;

        const form = this;
        const formData = {
            name: form.querySelector('#name').value,
            email: form.querySelector('#email').value,
            message: form.querySelector('#message').value,
        };

        try {
            await emailjs.send(
                "service_7k0ixzj",
                "template_3rlzwxj",
                {
                    from_name: formData.name,
                    from_email: formData.email,
                    message: formData.message,
                    to_name: "Akhil",
                    to_email: "akhil@modrnmagic.app"
                }
            );

            // Show success message
            form.innerHTML = `
                <div class="text-center py-8">
                    <svg class="w-16 h-16 text-green-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3 class="text-2xl font-bold mb-2">Message Sent Successfully!</h3>
                    <p class="text-gray-500">We'll get back to you within 24 hours.</p>
                </div>
            `;
        } catch (error) {
            console.error('Error:', error);
            // Show error message
            submitButton.disabled = false;
            submitButton.innerHTML = originalText;
            alert('Failed to send message. Please try again later.');
        }
    });
})();
