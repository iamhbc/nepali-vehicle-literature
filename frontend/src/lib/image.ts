// Downscale and re-encode on the device before upload: faster on slow networks
// and drops EXIF/GPS metadata before the photo leaves the phone.
export async function compressImage(file: File, maxSide = 1600, quality = 0.85): Promise<Blob> {
  if (!file.type.startsWith("image/")) throw new Error("Please choose an image file.");
  let bitmap: ImageBitmap | HTMLImageElement;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" } as ImageBitmapOptions);
  } catch {
    bitmap = await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("We couldn't open that photo."));
      img.src = URL.createObjectURL(file);
    });
  }
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const c = canvas.getContext("2d");
  if (!c) return file;
  c.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  return blob ?? file;
}
