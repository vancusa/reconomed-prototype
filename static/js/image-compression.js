// static/js/image-compression.js
class ImageCompressor {
    constructor(options = {}) {
        this.maxSizeMB = options.maxSizeMB || 2;
        this.maxWidth = options.maxWidth || 2048;
        this.maxHeight = options.maxHeight || 2048;
        this.quality = options.quality || 0.8;
    }

    async compressFile(file) {
        return new Promise((resolve, reject) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();

            img.onload = () => {
                // Calculate new dimensions
                let { width, height } = this.calculateDimensions(img.width, img.height);
                
                canvas.width = width;
                canvas.height = height;

                // Draw and compress
                ctx.drawImage(img, 0, 0, width, height);
                
                canvas.toBlob((blob) => {
                    if (blob) {
                        // Create new file with compressed data
                        const compressedFile = new File([blob], file.name, {
                            type: file.type,
                            lastModified: Date.now()
                        });
                        resolve(compressedFile);
                    } else {
                        resolve(file); // Fallback to original
                    }
                }, file.type, this.quality);
            };

            img.onerror = () => resolve(file); // Fallback to original
            img.src = URL.createObjectURL(file);
        });
    }

    calculateDimensions(width, height) {
        const ratio = width / height;
        
        if (width > this.maxWidth) {
            width = this.maxWidth;
            height = width / ratio;
        }
        
        if (height > this.maxHeight) {
            height = this.maxHeight;
            width = height * ratio;
        }
        
        return { width: Math.round(width), height: Math.round(height) };
    }

    async compressMultiple(files, onProgress = null) {
        const compressed = [];
        
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            if (onProgress) onProgress(i, files.length, file.name);
            
            const compressedFile = await this.compressFile(file);
            compressed.push({
                original: file,
                compressed: compressedFile,
                originalSize: file.size,
                compressedSize: compressedFile.size,
                compressionRatio: ((file.size - compressedFile.size) / file.size * 100).toFixed(1)
            });
        }
        
        return compressed;
    }
}

// Global instance
window.imageCompressor = new ImageCompressor();