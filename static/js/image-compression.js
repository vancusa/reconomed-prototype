// image-compression.js
// ES Module version
// Utility functions to compress images before uploading

/* *
 * Compress an image file using a <canvas>.
 * @param {File} file - The original image file
 * @param {Object} options - Compression options
 * @param {number} options.maxWidth - Max width for resized image
 * @param {number} options.maxHeight - Max height for resized image
 * @param {number} options.quality - Compression quality (0.0 - 1.0)
 * @returns {Promise<File>} - A new File object with compressed image
 */
export async function compressImage(file, { maxWidth = 1280, maxHeight = 1280, quality = 0.8 } = {}) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        
        reader.onload = event => {
            const img = new Image();
            img.onload = () => {
                let { width, height } = img;

                // Resize while keeping aspect ratio
                if (width > maxWidth || height > maxHeight) {
                    const ratio = Math.min(maxWidth / width, maxHeight / height);
                    width = width * ratio;
                    height = height * ratio;
                }

                // Draw image to canvas
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Export compressed blob
                canvas.toBlob(
                    blob => {
                        if (!blob) {
                            reject(new Error('Image compression failed.'));
                            return;
                        }
                        const compressedFile = new File([blob], file.name, { type: file.type });
                        resolve(compressedFile);
                    },
                    file.type,
                    quality
                );
            };
            img.onerror = () => reject(new Error('Image loading failed.'));
            img.src = event.target.result;
        };

        reader.onerror = () => reject(new Error('File reading failed.'));
        reader.readAsDataURL(file);
    });
}