// /redux/actions/index.js`
// import { myMSALObj } from '../../services/auth';



export const setCurrentProject = (currentProject) => {
    localStorage.setItem('currentProject', JSON.stringify(currentProject));

    return {
        type: 'SET_CURRENT_PROJECT',
        currentProject
    }
}

export const setCurrentFileContext = (currentFileContext) => {
    localStorage.setItem('currentFileContext', JSON.stringify(currentFileContext));

    return {
        type: 'SET_CURRENT_FILE_CONTEXT',
        currentFileContext
    }
}

export const setCurrentFileContextLength = (currentFileContextLength) => {
    localStorage.setItem('currentFileContextLength', currentFileContextLength);

    return {
        type: 'SET_CURRENT_FILE_CONTEXT_LENGTH',
        currentFileContextLength
    }
}

export const setProjectList = (projectList) => {
    localStorage.setItem('projectList', JSON.stringify(projectList));

    return {
        type: 'SET_PROJECT_LIST',
        projectList
    }
}

// export const setChatSlidingWindow = (chatSlidingWindow) => ({
//     type: 'SET_SLIDING_WINDOW',
//     chatSlidingWindow
// })
//
// export const setDataStore = (useDataStore) => ({
//     type: 'SET_DATA_STORE',
//     useDataStore
// })

export const setModel = (useModel) => {
    localStorage.setItem('model', useModel);
    return {
        type: 'SET_MODEL',
        useModel
    }
}
export const setUseModelAlternatives = (useModelAlternatives) => {
    localStorage.setItem('modelAlternatives', JSON.stringify(useModelAlternatives));
    return {
        type: 'SET_MODEL_ALTERNATIVES',
        useModelAlternatives
    }
}

export const setModelList = (modelList) => ({
    type: 'SET_MODEL_LIST',
    modelList
})

export const setOpenModelList = (openModelList) => ({
    type: 'SET_OPEN_MODEL_LIST',
    openModelList
})

// export const setTemperature = (temperature) => {
//     localStorage.setItem('temperature', temperature);
//     return {
//         type: 'SET_TEMPERATURE',
//         temperature
//     }
// }

export const setAgent = (useAgent) => ({
    type: 'SET_AGENT',
    useAgent
})


// export const setUsePremiumModel = (usePremiumModel) => ({
//     type: 'SET_USE_PREMIUM_MODEL',
//     usePremiumModel
// })

// export const setProjectCount = (projectCount) => ({
//     type: 'SET_PROJECT_COUNT',
//     projectCount
// });

// export const setLoading = (loading) => ({
//     type: 'SET_LOADING',
//     loading
// });

export const setErrorMessage = (errorMessage) => {
    const error = new Error();
    console.log( 'error message: ', errorMessage);
    console.log( error.stack || error.stacktrace);

    return {
        type: 'SET_ERROR_MESSAGE',
        errorMessage
    }
}

export const setInfoMessage = (infoMessage) => ({
    type: 'SET_INFO_MESSAGE',
    infoMessage
});

export const setCurrentChatId = (currentChatId) => ({
    type: 'SET_CURRENT_CHAT_ID',
    currentChatId
})

export const setShowFilesNav = (showFilesNav) => ({
    type: 'SET_SHOW_FILES_NAV',
    showFilesNav
})

export const setShowNav = (showNav) => ({
    type: 'SET_SHOW_NAV',
    showNav
})

export const setIsMobile = (isMobile) => ({
    type: 'SET_IS_MOBILE',
    isMobile
})

export const setRetryLogin = (retryLogin) => ({
    type: 'SET_RETRY_LOGIN',
    retryLogin
})

export const setForceLogin = (isForceLogin) => ({
    type: 'SET_FORCE_LOGIN',
    isForceLogin
})

export const setTenantName = (tenantName) => ({
    type: 'SET_TENANT_NAME',
    tenantName
})

export const setUseMaximize = (useMaximize) => ({
    type: 'SET_USE_MAXIMIZE',
    useMaximize
})

export const setBalance = (balance) => ({
    type: 'SET_BALANCE',
    balance
})
export const setCurrentUsage = (currentUsage) => ({
    type: 'SET_CURRENT_USAGE',
    currentUsage
})

export const setChatLayout = (chatLayout) => {
    localStorage.setItem('layout', chatLayout);

    return {
        type: 'SET_CHAT_LAYOUT',
        chatLayout
    }
}

export const setCodeEditor = (isCodeEditor) => {
    localStorage.setItem('isCodeEditor', isCodeEditor);

    return {
        type: 'SET_CODE_EDITOR',
        isCodeEditor
    }
}

export const setDisableFromat = (isDisableFormat) => {
    localStorage.setItem('isDisableFormat', isDisableFormat);

    return {
        type: 'SET_DISABLE_FORMAT',
        isDisableFormat
    }
}

// export const setShowSysMessage = (showSysMessage) => {
//     localStorage.setItem('showSysMessage', showSysMessage);
//
//     return {
//         type: 'SET_SHOW_SYS_MESSAGE',
//         showSysMessage
//     }
// }

export const setShowOnTop = (showOnTop) => {
    localStorage.setItem('showOnTop', showOnTop);

    return {
        type: 'SET_SHOW_ON_TOP',
        showOnTop
    }
}


export const setProfile = (profile) => ({
    type: 'SET_PROFILE',
    profile
})

// export const setLoggedUsing = (loggedUsing) => {
//     localStorage.setItem('logged-using', loggedUsing);
//     console.log('setLoggedUsing to : ', loggedUsing);
//
//     return {
//         type: 'SET_LOGGED_USING',
//         loggedUsing
//     }
// }


// export const setToken = (token) => ({
//     type: 'SET_TOKEN',
//     token
// })

export const setWaiting = (waiting) => ({
    type: 'SET_WAITING',
    waiting
})

export const setResizeDetected = (resizeDetected) => ({
    type: 'SET_RESIZE_DETECTED',
    resizeDetected
})

export const setForceRefreshHistory = (forceRefreshHistory) => ({
    type: 'SET_FORCE_REFRESH_HISTORY',
    forceRefreshHistory
})
//
// export const setUseSearch = (useSearch) => ({
//     type: 'SET_USE_SEARCH',
//     useSearch
// })
//
// export const setUseCode = (useCode) => ({
//     type: 'SET_USE_CODE',
//     useCode
// })
//
// export const setUseImageGeneration = (useImageGeneration) => ({
//     type: 'SET_USE_IMAGE_GENERATION',
//     useImageGeneration
// })

// export const setUseUrlContext = (useUrlContext) => ({
//     type: 'SET_USE_URL_CONTEXT',
//     useUrlContext
// })

export const setAgenticMode = (agenticMode) => ({
    type: 'SET_AGENTIC_MODE',
    agenticMode
})

export const setShowMultiColumn = (showMultiColumn) => ({
    type: 'SET_SHOW_MULTI_COLUMN',
    showMultiColumn
})

export const setPreferences = (preferences) => {
    localStorage.setItem("preferences", JSON.stringify(preferences));
    return {
        type: "SET_PREFERENCES",
        preferences,
    }
}

export const setTemporaryChat = (temporaryChat) => ({
    type: 'SET_TEMPORARY_CHAT',
    temporaryChat
})
