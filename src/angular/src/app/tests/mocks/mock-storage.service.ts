import { StorageService, StorageTranscoder } from 'ngx-webstorage-service';

/**
 * Mock implementation of StorageService for testing.
 * Provides an in-memory storage that can be spied on.
 */
export class MockStorageService implements StorageService<any> {
    private storage: Map<string, any> = new Map();

    has(key: string): boolean {
        return this.storage.has(key);
    }

    get(key: string): any {
        return this.storage.get(key);
    }

    set(key: string, value: any): void {
        this.storage.set(key, value);
    }

    remove(key: string): void {
        this.storage.delete(key);
    }

    clear(): void {
        this.storage.clear();
    }

    withDefaultTranscoder<X>(_transcoder: StorageTranscoder<X>): StorageService<X> {
        return this as unknown as StorageService<X>;
    }
}
