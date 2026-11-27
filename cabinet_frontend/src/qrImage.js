import jsQR from 'jsqr';

// Reads the signed label content from a photo or PNG of the QR, fully in the browser.
// The server still verifies the signature, custody step and role.
export async function decodeQrFile(file) {
  if (!file?.size || file.size > 10 * 1024 * 1024) throw new Error('Choisissez une image du QR de 10 Mo maximum.');
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  const context = canvas.getContext('2d', { willReadFrequently: true });
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const image = context.getImageData(0, 0, canvas.width, canvas.height);
  const result = jsQR(image.data, image.width, image.height, { inversionAttempts: 'attemptBoth' });
  if (!result?.data) throw new Error('Aucun QR lisible dans cette image. Reprenez une photo nette du QR.');
  return result.data;
}
