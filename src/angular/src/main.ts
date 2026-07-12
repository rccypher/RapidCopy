import { platformBrowserDynamic } from '@angular/platform-browser-dynamic';

import { AppModule } from './app/app.module';
import { ApiKeyInterceptor } from './app/services/utils/api-key.interceptor';

// The server injects the API key into index.html's meta tag. Pick it up so the
// UI can authenticate its own API calls. External/script callers must supply the
// key themselves. (An unreplaced placeholder means no auth is configured.)
const injectedKey = document.querySelector('meta[name="rapidcopy-api-key"]')?.getAttribute('content') || '';
if (injectedKey && injectedKey !== '__RAPIDCOPY_API_KEY__') {
  ApiKeyInterceptor.setApiKey(injectedKey);
}

platformBrowserDynamic().bootstrapModule(AppModule, {
  ngZoneEventCoalescing: true
})
  .catch(err => console.error(err));
