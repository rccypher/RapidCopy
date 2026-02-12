declare let spyOn: any;

/**
 * Mock EventSource for testing. Does not implement the full EventSource interface
 * to avoid TypeScript complexity with overloaded methods.
 */
export class MockEventSource {
    url: string;
    onopen: ((event: Event) => any) | null = null;
    onerror: ((event: Event) => any) | null = null;
    onmessage: ((event: MessageEvent) => any) | null = null;

    eventListeners: Map<string, (event: MessageEvent) => void> = new Map();

    // EventSource constants
    readonly CONNECTING: number = 0;
    readonly OPEN: number = 1;
    readonly CLOSED: number = 2;

    readyState: number = 0;
    withCredentials: boolean = false;

    constructor(url: string, _eventSourceInitDict?: EventSourceInit) {
        this.url = url;
    }

    addEventListener(type: string, listener: (event: MessageEvent) => void, _options?: boolean | AddEventListenerOptions) {
        this.eventListeners.set(type, listener);
    }

    removeEventListener(_type: string, _listener: (event: MessageEvent) => void, _options?: boolean | EventListenerOptions) {}

    dispatchEvent(_event: Event): boolean {
        return true;
    }

    close() {
        this.readyState = this.CLOSED;
    }
}

export function createMockEventSource(url: string): MockEventSource {
    let mockEventSource = new MockEventSource(url);
    spyOn(mockEventSource, 'addEventListener').and.callThrough();
    spyOn(mockEventSource, 'close').and.callThrough();
    return mockEventSource;
}
