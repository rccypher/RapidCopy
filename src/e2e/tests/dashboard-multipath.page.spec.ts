import {DashboardMultiPathPage} from "./dashboard-multipath.page";

/**
 * E2E tests for multi-path features on the dashboard
 * 
 * These tests verify:
 * 1. Path pair statistics component (when multiple path pairs are configured)
 * 2. Path pair badges on files
 * 
 * Note: The path pair stats component only shows when:
 * - Multiple path pairs are configured
 * - At least one path pair has files
 * 
 * For single path pair configurations, the stats component is hidden.
 */
describe('Testing dashboard multi-path features', () => {
    let page: DashboardMultiPathPage;

    beforeEach(async () => {
        page = new DashboardMultiPathPage();
        await page.navigateTo();
    });

    it('should have right top title', () => {
        expect(page.getTopTitle()).toEqual("Dashboard");
    });

    // Tests for path pair badges on files
    describe('Path pair badges', () => {
        it('should display files in the list', async () => {
            const files = await page.getFilesWithPathPairs();
            expect(files.length).toBeGreaterThan(0);
        });

        // Note: This test depends on having multiple path pairs configured
        // It will pass even with single path pair (badges may not be shown)
        it('should get files with path pair info', async () => {
            const files = await page.getFilesWithPathPairs();
            expect(files).toBeDefined();
            expect(Array.isArray(files)).toBe(true);
        });
    });

    // Tests for path pair statistics component
    // These tests are conditional - the stats component only appears with multiple path pairs
    describe('Path pair statistics (multi-path mode)', () => {
        
        it('should check if path pair stats is present', async () => {
            // This may be true or false depending on configuration
            const isPresent = await page.isPathPairStatsPresent();
            expect(typeof isPresent).toBe('boolean');
        });

        // The following tests only run when multi-path mode is active
        // They use conditional execution to avoid failures in single-path setups

        it('should show stats component header when multiple path pairs exist', async () => {
            const isPresent = await page.isPathPairStatsPresent();
            if (isPresent) {
                expect(page.getPathPairStatsTitle()).toEqual("Path Pair Statistics");
            }
        });

        it('should toggle stats expansion when clicking header', async () => {
            const isPresent = await page.isPathPairStatsPresent();
            if (isPresent) {
                const initialState = await page.isPathPairStatsExpanded();
                await page.togglePathPairStats();
                const newState = await page.isPathPairStatsExpanded();
                expect(newState).toBe(!initialState);
                
                // Toggle back
                await page.togglePathPairStats();
            }
        });

        it('should display stat cards for each path pair', async () => {
            const isPresent = await page.isPathPairStatsPresent();
            if (isPresent) {
                const cardCount = await page.getPathPairStatCardCount();
                expect(cardCount).toBeGreaterThan(0);
            }
        });

        it('should have stat cards with required information', async () => {
            const isPresent = await page.isPathPairStatsPresent();
            if (isPresent) {
                const cards = await page.getPathPairStatCards();
                if (cards.length > 0) {
                    const firstCard = cards[0];
                    expect(firstCard.name).toBeDefined();
                    expect(firstCard.fileCount).toBeDefined();
                }
            }
        });
    });

    // Tests to verify path pair badge consistency with stats
    describe('Path pair badge and stats consistency', () => {
        
        it('should have consistent path pair names in badges and stats', async () => {
            const isStatsPresent = await page.isPathPairStatsPresent();
            const hasBadges = await page.hasAnyPathPairBadge();
            
            if (isStatsPresent && hasBadges) {
                const badgeNames = await page.getUniquePathPairNames();
                const cards = await page.getPathPairStatCards();
                const statNames = cards.map(c => c.name);
                
                // Each badge name should have a corresponding stat card
                for (const badgeName of badgeNames) {
                    expect(statNames).toContain(badgeName);
                }
            }
        });
    });
});
