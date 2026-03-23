import styles from "./Logo.module.css"
import {ThemeContext} from "../../redux/ThemeContext";
import React, {useContext, useEffect, useState} from "react";
import {RiAnthropicFill} from "react-icons/ri";
import {ReactComponent as XaiIcon} from "../../icons/grok.svg"
import {FaRobot} from "react-icons/fa";

function Logo({company}) {
    const { theme } = useContext(ThemeContext);

    switch (company) {
        case "OPENAI":
            return <div><img src= "/openai.png" alt={company}></img></div>
        case "XAI":
            // return <XaiIcon/>
            return <div style={{height: "100%", width:"100%"}}><XaiIcon/></div>
        case "GEMINI":
            return <div><img src="/gemini.png" alt={company}></img></div>
        case "MISTRAL":
            return <div><img src="/mistral.png" alt={company}></img></div>
        case "ANTHROPIC":
            return <RiAnthropicFill size={20} />
    }

    // fallback
    return (<FaRobot
        title={company}
    />)
}

export default Logo;

