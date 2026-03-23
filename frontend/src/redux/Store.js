// #/redux/Store.js

import { useReducer } from 'react';
import appReducer from './reducers';

export const useStore = (initialState) => useReducer(appReducer, initialState);
// export const useStore = () => useReducer(appReducer);
