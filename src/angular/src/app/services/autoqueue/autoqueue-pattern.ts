import {Record} from "immutable";

interface IAutoQueuePattern {
    pattern: string;
}
const DefaultAutoQueuePattern: IAutoQueuePattern = {
    pattern: null
};
const AutoQueuePatternRecord = Record(DefaultAutoQueuePattern);


export class AutoQueuePattern extends AutoQueuePatternRecord implements IAutoQueuePattern {
    constructor(props) {
        super(props);
    }

    // Use getters to properly access Record values (Immutable.js 4.x compatibility)
    get pattern(): string {
        return this.get("pattern");
    }
}

/**
 * ServerStatus as serialized by the backend.
 * Note: naming convention matches that used in JSON
 */
export interface AutoQueuePatternJson {
    pattern: string;
}
