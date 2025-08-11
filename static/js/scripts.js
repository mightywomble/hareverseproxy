// Modern glass panel interface enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Add subtle animations to cards on scroll
    const cards = document.querySelectorAll('.card');
    
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const cardObserver = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);
    
    cards.forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        cardObserver.observe(card);
    });
    
    // Add ripple effect to buttons
    const buttons = document.querySelectorAll('.btn');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.height, rect.width);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // Enhanced form focus effects
    const formControls = document.querySelectorAll('.form-control');
    
    formControls.forEach(control => {
        control.addEventListener('focus', function() {
            this.parentElement.classList.add('focused');
        });
        
        control.addEventListener('blur', function() {
            this.parentElement.classList.remove('focused');
        });
    });
    
    // Smooth scroll for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading states to async operations
    const loadingStates = new Map();
    
    window.setLoadingState = function(element, isLoading) {
        const elementId = element.id || Math.random().toString(36).substr(2, 9);
        
        if (isLoading && !loadingStates.has(elementId)) {
            const originalText = element.textContent;
            loadingStates.set(elementId, originalText);
            element.innerHTML = '<i class="spinner-border spinner-border-sm me-2" role="status"></i>Loading...';
            element.disabled = true;
        } else if (!isLoading && loadingStates.has(elementId)) {
            element.textContent = loadingStates.get(elementId);
            element.disabled = false;
            loadingStates.delete(elementId);
        }
    };
    
    // Enhanced hover effects for interactive elements
    const interactiveElements = document.querySelectorAll('.btn, .card, .accordion-button, .nav-link');
    
    interactiveElements.forEach(element => {
        element.addEventListener('mouseenter', function() {
            this.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        });
        
        element.addEventListener('mouseleave', function() {
            this.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        });
    });
});

// CSS for ripple effect
if (!document.querySelector('#ripple-styles')) {
    const rippleStyles = document.createElement('style');
    rippleStyles.id = 'ripple-styles';
    rippleStyles.textContent = `
        .btn {
            position: relative;
            overflow: hidden;
        }
        
        .ripple {
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: scale(0);
            animation: ripple-animation 0.6s linear;
            pointer-events: none;
        }
        
        @keyframes ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
        
        .focused {
            transform: scale(1.02);
        }
        
        .spinner-border-sm {
            width: 1rem;
            height: 1rem;
            border-width: 0.1em;
        }
        
        .spinner-border {
            display: inline-block;
            border: 0.2em solid currentColor;
            border-right-color: transparent;
            border-radius: 50%;
            animation: spinner-border-animation 0.75s linear infinite;
        }
        
        @keyframes spinner-border-animation {
            to {
                transform: rotate(360deg);
            }
        }
    `;
    document.head.appendChild(rippleStyles);
}
