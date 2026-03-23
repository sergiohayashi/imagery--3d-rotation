import styles from "./ManagerTop.module.css"
import React, {useContext} from "react";
import {Link, Route, Routes, useNavigate} from "react-router-dom";
import {ThemeContext} from "../../redux/ThemeContext";
// import ManagerFeedback from "../ManagerFeedback/ManagerFeedback";
import ManagerMetrics from "../ManagerMetrics/ManagerMetrics";
import ExternalUser from "../ExternalUser/ExternalUser";
import {AppContext} from "../../redux/AppContext";
import config from "../../config";
import {FaAngleLeft} from "react-icons/fa";
import {Title} from "../Headings/Heading";


// Users.js
const Users = () => {
    return <div>Users Page</div>;
};


const Feedback = () => {
    return <div>Feedback Page</div>;
};


function ManagerTop() {
    const { theme } = useContext(ThemeContext);
    const navigate = useNavigate();
    const { state, dispatch } = useContext(AppContext);
    const {profile} = state;

    if (!profile?.permissions.includes('manager')) {
        navigate("/chat");
        return <div>Oops, nothing here</div>;
    }

    return (
        <div className={styles['container']}>
            {/*<div className={"title-with-back"}>*/}
            {/*    <a onClick={() => navigate(-1)} className={"fa-icon"}>*/}
            {/*        <FaAngleLeft/>*/}
            {/*    </a>*/}
            {/*    <Title>Manager</Title>*/}
            {/*</div>*/}
            <div className={styles['manager-container']}>
                <div className={styles['manager-container-left']}>
                    {/*<div><Link to="feedback">Feedback</Link></div>*/}
                    <div><Link to="external-user">External User</Link></div>
                    <div><Link to="manager-metrics">Metrics</Link></div>
                    {/*<div><Link to="users">Users</Link></div>*/}
                </div>
                <div className={styles['manager-container-right']}>
                    <Routes>
                        {/*<Route path="feedback" element={<ManagerFeedback/>}/>*/}
                        <Route path="external-user" element={<ExternalUser/>}/>
                        <Route path="manager-metrics" element={<ManagerMetrics/>}/>
                        {/*<Route path="users" element={<Users/>}/>*/}
                        {/* Add more sub-routes here as needed */}
                    </Routes>
                </div>
            </div>
        </div>
    )
}


export default ManagerTop;
