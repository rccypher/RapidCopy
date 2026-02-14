// Re-export all page objects
export { BasePage } from '../fixtures';
export { DashboardPage } from './dashboard.page';
export { SettingsPage } from './settings.page';
export { AutoQueuePage } from './autoqueue.page';
export { AboutPage } from './about.page';
export { LogsPage } from './logs.page';

// Re-export types
export type { FileInfo, FileActionButton } from './dashboard.page';
export type { PathPairItem } from './settings.page';
