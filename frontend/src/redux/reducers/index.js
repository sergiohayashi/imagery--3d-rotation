// /redux/reducers/index.js`

const initialState = {}
//     currentProject: null,
//     errorMessage: null,
//     projectList: [],
//     isLoading: false,
//     account: null,
//     isLoggedIn: false,
//     showNav: !window.matchMedia("(max-width: 768px)").matches,
//     isMobile: window.matchMedia("(max-width: 768px)").matches,
//     chatSlidingWindow: false,
//     useAgent: null,
//     chatLayout: localStorage.getItem('layout') || "column",
// };


export default function appReducer(state = initialState, action) {
    if (!action) {
        const error = new Error("Stack trace in appReducer:");
        console.log(error.stack);
        return state;
    }

    switch (action.type) {
        case 'SET_CURRENT_PROJECT':
            return {...state, currentProject: action.currentProject};
        case 'SET_PROJECT_LIST':
            return {...state, projectList: action.projectList};
        // case 'SET_PROJECT_COUNT':
        //     return {...state, projectCount: action.projectCount};
        case 'SET_LOADING':
            return {...state, isLoading: action.loading};
        case 'SET_ACCOUNT':
            return {...state, account: action.account};
        case 'UPDATE_LOGGED_IN':
            return {...state, isLoggedIn: action.isLoggedIn};
        case 'SET_ERROR_MESSAGE':
            return {...state, errorMessage: action.errorMessage};
        case 'SET_INFO_MESSAGE':
            return {...state, infoMessage: action.infoMessage};
        case 'SET_CURRENT_CHAT_ID':
            return {...state, currentChatId: action.currentChatId};
        case 'SET_SHOW_NAV':
            return {...state, showNav: action.showNav};
        case 'SET_SHOW_FILES_NAV':
            return {...state, showFilesNav: action.showFilesNav};
        case 'SET_IS_MOBILE':
            return {...state, isMobile: action.isMobile};
        case 'SET_CURRENT_USAGE':
            return {...state, currentUsage: action.currentUsage};
        case 'SET_RETRY_LOGIN':
            return {...state, retryLogin: action.retryLogin};
        case 'SET_FORCE_LOGIN':
            return {...state, isForceLogin: action.isForceLogin};
        case 'SET_SLIDING_WINDOW':
            return {...state, chatSlidingWindow: action.chatSlidingWindow};
        // case 'SET_USE_PREMIUM_MODEL':
        //     return {...state, usePremiumModel: action.usePremiumModel};
        case 'SET_DATA_STORE':
            return {...state, useDataStore: action.useDataStore};
        case 'SET_MODEL':
            return {...state, useModel: action.useModel};
        case 'SET_MODEL_ALTERNATIVES':
            return {...state, useModelAlternatives: action.useModelAlternatives};
        // case 'SET_TEMPERATURE':
        //     return {...state, temperature: action.temperature};
        case 'SET_AGENT':
            return {...state, useAgent: action.useAgent};
        case 'SET_USE_MAXIMIZE':
            return {...state, useMaximize: action.useMaximize};
        case 'SET_BALANCE':
            return {...state, balance: action.balance};
        case 'SET_CHAT_LAYOUT':
            return {...state, chatLayout: action.chatLayout};
        case 'SET_CODE_EDITOR':
            return {...state, isCodeEditor: action.isCodeEditor};
        case 'SET_MODEL_LIST':
            return {...state, modelList: action.modelList};
        case 'SET_OPEN_MODEL_LIST':
            return {...state, openModelList: action.openModelList};
        case 'SET_TENANT_NAME':
            return {...state, tenantName: action.tenantName};
        case 'SET_PROFILE':
            return {...state, profile: action.profile};
        case 'SET_DISABLE_FORMAT':
            return {...state, isDisableFormat: action.isDisableFormat};
        case 'SET_SHOW_SYS_MESSAGE':
            return {...state, showSysMessage: action.showSysMessage};
        case 'SET_SHOW_ON_TOP':
            return {...state, showOnTop: action.showOnTop};
        case 'SET_RESIZE_DETECTED':
            return {...state, resizeDetected: action.resizeDetected};
        case 'SET_FORCE_REFRESH_HISTORY':
            return {...state, forceRefreshHistory: action.forceRefreshHistory};
        case 'SET_CURRENT_FILE_CONTEXT':
            return {...state, currentFileContext: action.currentFileContext};
        case 'SET_CURRENT_FILE_CONTEXT_LENGTH':
            return {...state, currentFileContextLength: action.currentFileContextLength};

        // case 'SET_LOGGED_USING':
        //     return {...state, loggedUsing: action.loggedUsing};
        // case 'SET_TOKEN':
        //     return {...state, token: action.token};
        case 'SET_WAITING':
            return {...state, waiting: action.waiting};
        // case 'SET_USE_SEARCH':
        //     return {...state, useSearch: action.useSearch};
        // case 'SET_USE_URL_CONTEXT':
        //     return {...state, useUrlContext: action.useUrlContext};
        // case 'SET_USE_CODE':
        //     return {...state, useCode: action.useCode};
        // case 'SET_USE_IMAGE_GENERATION':
        //     return {...state, useImageGeneration: action.useImageGeneration};
        case 'SET_AGENTIC_MODE':
            return {...state, agenticMode: action.agenticMode};
        case 'SET_SHOW_MULTI_COLUMN':
            return {...state, showMultiColumn: action.showMultiColumn};
        case 'SET_PREFERENCES':
            return {...state, preferences: action.preferences};
        // case 'SET_RANKING':
        //     return {...state, ranking: action.ranking};
        case 'SET_TEMPORARY_CHAT':
            return {...state, temporaryChat: action.temporaryChat};
        default:
            throw new Error(`Unknown action: ${action.type}`);
    }
}


