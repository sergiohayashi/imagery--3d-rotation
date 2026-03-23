// src/FullMarkdown.js
import React, {useContext} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';
import remarkMath from "remark-math";
import supersub from "remark-supersub";
import rehypeRaw from "rehype-raw";
import {ThemeContext} from "../../redux/ThemeContext";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { twilight, vs, oneLight, oneDark, materialLight} from 'react-syntax-highlighter/dist/esm/styles/prism';
import styles from "./FullMarkdown.module.css";
import {setErrorMessage, setInfoMessage} from "../../redux/actions";
import {AppContext} from "../../redux/AppContext";
import {FaCopy} from "react-icons/fa6";

// https://github.com/orgs/remarkjs/discussions/1121
// https://stackoverflow.com/questions/71907116/react-markdown-and-react-syntax-highlighter

const p = React.memo(({ children }) => {
    return <p className="whitespace-pre-wrap">{children}</p>;
});

const FullMarkdownNoMath = ({ content }) => {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);

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

    const extractCode = (children) => {
        if (Array.isArray(children)) {
            return children
                .map((child) => {
                    const val =
                        typeof child === 'object'
                            ? extractCode(child?.props?.children)
                            : child;
                    return val;
                })
                .join('');
        } else if (typeof children === 'object' && children !== null) {
            // Handle the case where children is a single React element
            return extractCode(children.props?.children);
        } else {
            // Handle the case where children is a string or other primitive type
            return children;
        }
    };


    return (
        <ReactMarkdown
            children={content}
            remarkPlugins={[supersub, remarkGfm]}
            rehypePlugins={[[rehypeKatex],
                [
                    rehypeHighlight,
                    {
                        detect: true,
                        ignoreMissing: true,
                    },
                ],
                [rehypeRaw]]}
            components={{
                p,
                code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    let rawCode = extractCode(children);
                    return !inline && match ? (<div className={styles["code-block"]}>
                            <div className={styles["code-icons"]}>
                                <div className={`${styles["copy-paste"]} fa-icon -smaller`}
                                     onClick={() => handleCopyContent(rawCode)}
                                     title={"copy to clipboard"}
                                >
                                    <FaCopy/>
                                </div>
                            </div>
                            <div className={styles["code-part"]}>
                                <SyntaxHighlighter style={theme === 'dark' ? twilight : vs} PreTag="div"
                                                   language={match[1]} {...props}>
                                    {rawCode}
                                    {/*{String(children).replace(/\n$/, '')}*/}
                                </SyntaxHighlighter>
                            </div>
                        </div>
                    ) : (<code className={className} {...props}>
                            {children}
                        </code>
                    );
                },
            }}
        />
    );
};

export default FullMarkdownNoMath;
