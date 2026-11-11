const PREFIX = "resiq-upload:";

function openImages() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open("resiq-demo-images", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("images");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function imageOperation<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>) {
  const db = await openImages();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = db.transaction("images", mode);
      const request = run(transaction.objectStore("images"));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onabort = () => reject(transaction.error ?? request.error);
    });
  } finally {
    db.close();
  }
}

export async function storeImage(id: string, file: Blob) {
  await imageOperation("readwrite", (store) => store.put(file, id));
  return PREFIX + id;
}

export function removeImage(id: string) {
  return imageOperation("readwrite", (store) => store.delete(id));
}

export function isStoredImage(src: string) {
  return src.startsWith(PREFIX);
}

export function readImage(src: string) {
  return imageOperation<Blob | undefined>("readonly", (store) => store.get(src.slice(PREFIX.length)));
}
