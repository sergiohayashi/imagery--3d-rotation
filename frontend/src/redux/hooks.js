// /redux/hooks.js
import { useContext } from 'react';
import { AppContext } from './AppContext';
import { setErrorMessage, setInfoMessage } from './actions';

export function useErrorMessage() {
    const {dispatch} = useContext(AppContext);

    const setMessage = (message) => {
        dispatch(setErrorMessage(message));
    };

    return { setMessage };
}


export function useInfoMessage() {
    const {dispatch} = useContext(AppContext);

    const setMessage = (message) => {
        dispatch(setInfoMessage(message));
    };

    return { setMessage };
}
