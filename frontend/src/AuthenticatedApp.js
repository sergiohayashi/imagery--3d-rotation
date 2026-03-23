import Login from "./components/Login/Login";
import TopMostLayout from "./components/TopMostLayout/TopMostLayout";

import {StatusLoginValues, useAuth} from './context/AuthContext';
import Loading from "./components/Loading/Loading";

function AuthenticatedApp() {
    const { statusLogin } = useAuth();

    // if (
    //     statusLogin === StatusLoginValues.INITIALIZING ||
    //     statusLogin === StatusLoginValues.UNDEFINED || // If UNDEFINED is a specific string value
    //     statusLogin === StatusLoginValues.LOGGED_IN_WAITING_REGISTER ||
    //     !statusLogin // Catches cases where statusLogin might be null or truly undefined
    // ) {
    //     return (<></>);
    // }

    switch(statusLogin) {
        case StatusLoginValues.REGISTER_FAILED:
        case StatusLoginValues.LOGGED_OUT:
            // return <Login />;

        case StatusLoginValues.REGISTERED:
            return <>Hi!</>;
            // return <TopMostLayout />;
    }
}

export default AuthenticatedApp;
