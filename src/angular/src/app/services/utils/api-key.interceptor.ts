import {Injectable} from "@angular/core";
import {HttpEvent, HttpHandler, HttpInterceptor, HttpRequest} from "@angular/common/http";
import {Observable} from "rxjs";

/**
 * ApiKeyInterceptor injects the X-Api-Key header into every outgoing
 * HTTP request to the backend (/server/*).
 *
 * The key is stored in localStorage under "rapidcopy.api_key" and is
 * populated by the ConfigService when the config is first loaded.
 * An empty key means auth is disabled — no header is injected.
 */
@Injectable()
export class ApiKeyInterceptor implements HttpInterceptor {
    static readonly STORAGE_KEY = "rapidcopy.api_key";

    static setApiKey(key: string) {
        if (key) {
            localStorage.setItem(ApiKeyInterceptor.STORAGE_KEY, key);
        } else {
            localStorage.removeItem(ApiKeyInterceptor.STORAGE_KEY);
        }
    }

    static getApiKey(): string {
        return localStorage.getItem(ApiKeyInterceptor.STORAGE_KEY) || "";
    }

    intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
        const apiKey = ApiKeyInterceptor.getApiKey();
        if (apiKey && req.url.includes("/server/")) {
            const authReq = req.clone({
                setHeaders: {"X-Api-Key": apiKey}
            });
            return next.handle(authReq);
        }
        return next.handle(req);
    }
}
