import {useContext, useMemo} from 'react';
import axios from 'axios';
import config from '../config';
import {useAuth} from '../context/AuthContext';
import {AppContext} from '../redux/AppContext';
import {setErrorMessage, setForceLogin, setWaiting} from '../redux/actions';

export const useApi = () => {
    const { getToken, resetLogin } = useAuth();
    const { dispatch } = useContext(AppContext);

    // Use useMemo to ensure the Axios instance is stable across renders
    return useMemo(() => {
        const instance = axios.create({
            baseURL: config.apiUrl,
        });

        instance.interceptors.request.use(async (config) => {
                dispatch(setWaiting(true));
                const token = await getToken();
                config.headers.Authorization = `Bearer ${token}`;
                return config;
            }
            // ,(error) => Promise.reject(error)   //TODO: Precisa?
        );

        instance.interceptors.response.use(
            response => {
                dispatch(setWaiting(false));
                return response;
            },
            error => {
                dispatch(setWaiting(false));
                if (error.response?.data?.detail) {
                    try {
                        dispatch(setErrorMessage(error.response.data.detail.map(item => item.msg).join(",")));
                    } catch (ignore) {
                        dispatch(setErrorMessage(error.response.data.detail));
                    }
                } else if (error.response?.data) {
                    dispatch(setErrorMessage(error.response.data));
                } else {
                    dispatch(setErrorMessage(error.response?.data?.message || error.message));
                }

                if (error.response && error.response.status === 401) { //} || error.response.status === 403)) {
                    console.log( "Error! Force reevaluate login status", error);
                    resetLogin();
                }
                return Promise.reject(error);
            },
        );

        return instance;
    }, [dispatch]);
};
