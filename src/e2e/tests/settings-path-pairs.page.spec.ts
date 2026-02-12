import {SettingsPathPairsPage} from "./settings-path-pairs.page";

describe('Testing path pairs management on settings page', () => {
    let page: SettingsPathPairsPage;

    beforeEach(async () => {
        page = new SettingsPathPairsPage();
        await page.navigateTo();
    });

    it('should have the path pairs section', () => {
        expect(page.getPathPairsSectionTitle()).toEqual("Path Pairs");
    });

    it('should have an Add Path Pair button', () => {
        expect(page.isAddButtonPresent()).toBe(true);
    });

    it('should show form when clicking Add Path Pair button', async () => {
        await page.clickAddButton();
        expect(page.isFormDisplayed()).toBe(true);
        expect(page.getFormTitle()).toEqual("New Path Pair");
    });

    it('should hide form when clicking Cancel', async () => {
        await page.clickAddButton();
        expect(page.isFormDisplayed()).toBe(true);
        await page.clickCancel();
        expect(page.isFormDisplayed()).toBe(false);
    });

    // Note: The following tests require a test environment with writable path pairs config
    // They are marked with 'x' prefix to skip by default, enable in test environments
    
    xit('should create a new path pair', async () => {
        const initialCount = await page.getPathPairCount();
        
        await page.clickAddButton();
        page.fillForm("Test Pair", "/remote/test", "/local/test");
        await page.clickSave();
        
        // Wait for the form to close and list to update
        expect(page.isFormDisplayed()).toBe(false);
        expect(page.getPathPairCount()).toBe(initialCount + 1);
    });

    xit('should edit an existing path pair', async () => {
        // Assumes at least one path pair exists
        const pairs = await page.getPathPairs();
        if (pairs.length > 0) {
            await page.clickEditButton(0);
            expect(page.isFormDisplayed()).toBe(true);
            expect(page.getFormTitle()).toEqual("Edit Path Pair");
        }
    });

    xit('should toggle path pair enabled state', async () => {
        // Assumes at least one path pair exists
        const pairs = await page.getPathPairs();
        if (pairs.length > 0) {
            const initialState = pairs[0].isEnabled;
            await page.clickToggleButton(0);
            
            const updatedPairs = await page.getPathPairs();
            expect(updatedPairs[0].isEnabled).toBe(!initialState);
            
            // Toggle back
            await page.clickToggleButton(0);
        }
    });
});
