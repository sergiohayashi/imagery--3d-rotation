import styles from './Home.module.css'
import React, {useContext, useEffect} from "react";
import {setCurrentChatId} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import {useNavigate} from "react-router-dom";

function Home() {
    const { state, dispatch } = useContext(AppContext);
    const { currentProject } = state;
    const navigate = useNavigate();

    useEffect(() => {
        if (currentProject) {
            // dispatch(setCurrentChatId(null))
            navigate( `/chat`)
        }
    }, [currentProject]);


    return (
        <div className={styles["home-container"]}>
            <div className={styles["home-container-scroll"]}>
                <h1>Welcome to Imagery!</h1>
            </div>
        </div>
    )
}
export default Home;
