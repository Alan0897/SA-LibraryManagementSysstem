// site.js - small UI helpers
document.addEventListener('DOMContentLoaded', function(){
    // Initialize AOS if present
    if(window.AOS){ AOS.init({ duration: 650, once: true, easing: 'ease-out-cubic' }); }

    // Ensure Bootstrap carousels with data-bs-ride attribute start
    var carousels = document.querySelectorAll('.carousel[data-bs-ride]');
    carousels.forEach(function(c){
        // no-op: bootstrap auto init via data attributes when bundle loaded
    });
});
