import styles from "./CodeWithHighlighting.module.css"
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { twilight, vs, oneLight, oneDark, materialLight} from 'react-syntax-highlighter/dist/esm/styles/prism';
import React, {useContext} from 'react';
import {ThemeContext} from "../../redux/ThemeContext";
import TextWithFormulas from "../TextWithFormulas/TextWithFormulas";
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import {FaCodeBranch, FaCopy} from "react-icons/fa6";

const CodeWithHighlighting = ({ text }) => {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);

    if (!text) return null;

    const handleCopyContent = (content) => {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(content).then(() => {
                console.log('Content copied to clipboard');
                dispatch( setInfoMessage('Content copied to clipboard'));

                // Optionally, you can display a message to the user indicating the copy was successful.
            }).catch(err => {
                console.error('Could not copy text: ', err);
            });
        } else {
            setErrorMessage( "Not supported in this browser");
        }
    };



    // Regular expression to match code blocks
    const codeBlockRegex = /```(\w+)\s+([\s\S]*?)```/g;

    // Split the text into code and non-code segments
    const segments = [];
    let lastIndex = 0;
    text.replace(codeBlockRegex, (match, lang, code, index) => {
        // Push the text before the code block
        // if (index > lastIndex) {
        //     segments.push({ type: 'text', content: text.slice(lastIndex, index) });
        // }
        const textSegment = text.slice(lastIndex, index);
        if (textSegment) {
            // console.log( 'textSegment', textSegment);
            // Process the text segment for code highlighting
            segments.push({ type: 'text', content: <TextWithFormulas text={textSegment} />});
        }


        // Push the code block
        segments.push({ type: 'code', language: lang, content: code });
        lastIndex = index + match.length;
    });

    // Push the remaining text after the last code block
    if (lastIndex < text.length) {
        // segments.push({ type: 'text', content: text.slice(lastIndex) });

        const remainingText = text.slice(lastIndex);
        segments.push({ type: 'text', content: <TextWithFormulas text={remainingText} />});

    }

    // Render the segments with appropriate formatting
    const renderSegment = (segment, index) => {
        if (segment.type === 'code') {
            return (
                <div key={index} className={styles["code-block"]}>
                    <div onClick={() => handleCopyContent(segment.content)}
                         className={`${styles["copy-paste"]} fa-icon -smaller`} title={"copy to clipboard"}>
                        Hi
                        <FaCopy/>
                    </div>
                    <div>
                        Olá
                    <SyntaxHighlighter key={index} language={segment.language} style={theme === "dark" ? twilight : vs}>
                        {segment.content}
                    </SyntaxHighlighter></div>
                </div>

            );
        } else {
            // return <span key={index}>{segment.content}</span>;
            return <>{segment.content}</>;
        }
    };

    return <>{segments.map(renderSegment)}</>;
};

export default CodeWithHighlighting;
