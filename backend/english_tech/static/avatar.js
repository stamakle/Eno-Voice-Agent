class AIAvatar {
    constructor() {
        this.container = document.getElementById('omniverse-avatar');
        this.state = 'idle'; // idle, thinking, talking
        this.analyser = null;
        this.dataArray = null;

        if (!this.container) return;

        // Clear existing canvas if any
        this.container.innerHTML = '';
        
        // Setup simple image element
        this.img = document.createElement('img');
        this.img.src = '/static/avatar.png';
        this.img.alt = 'Aura AI Avatar';
        this.img.className = 'w-full h-full object-cover rounded-full transition-transform duration-100';
        this.container.appendChild(this.img);

        this.animate = this.animate.bind(this);
        this.animate();
    }

    setState(newState) {
        if (this.state === newState) return;
        this.state = newState;

        if (newState === 'idle') {
            this.container.style.boxShadow = '0 0 40px rgba(125, 224, 168, 0.1)';
        } else if (newState === 'thinking') {
            this.container.style.boxShadow = '0 0 50px rgba(66, 133, 244, 0.4)';
        } else if (newState === 'talking') {
            this.container.style.boxShadow = '0 0 60px rgba(37, 192, 244, 0.5)';
        }
    }

    startMonitoring(audioContext, sourceNode) {
        if (!audioContext || !sourceNode) return;
        this.analyser = audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        sourceNode.connect(this.analyser);
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    }

    stopMonitoring() {
        this.setState('idle');
        this.analyser = null;
        this.dataArray = null;
        this.img.style.transform = `scale(1.0)`;
    }

    animate() {
        requestAnimationFrame(this.animate);

        let targetScale = 1.0;

        if (this.state === 'talking' && this.analyser && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);
            let sum = 0;
            for (let i = 0; i < this.dataArray.length; i++) {
                sum += this.dataArray[i];
            }
            const average = sum / this.dataArray.length;
            const volume = average / 255;
            
            // Scale dynamically based on voice volume
            targetScale = 1.0 + (volume * 0.15); // Max 15% larger
            
            // Reactively pulse shadow based on volume
            this.container.style.boxShadow = `0 0 ${40 + (volume * 50)}px rgba(37, 192, 244, ${0.3 + volume * 0.5})`;
        } else if (this.state === 'thinking') {
            // Gentle continuous pulse
            const time = Date.now() / 1000;
            targetScale = 1.0 + Math.sin(time * 3) * 0.03;
        }

        // Apply scale directly to image
        if (this.img) {
            this.img.style.transform = `scale(${targetScale})`;
        }
    }
}

// Ensure it initializes after the script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.aiAvatar = new AIAvatar();
    });
} else {
    window.aiAvatar = new AIAvatar();
}
