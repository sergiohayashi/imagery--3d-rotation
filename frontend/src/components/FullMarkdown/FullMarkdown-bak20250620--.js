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

const preprocessContent = (markdown) => {
    // return markdown;  //TEST!

    //TODO: Este pre processamento serve para trocar notação de \[ par
    if (!!!markdown) return markdown;
    // markdown = markdown.replace(/(\$)(?=\s?\d)/g, '\\$');

    return markdown
        .replace(/\\\[(.*?)\\\]/gs, '$$$$ $1 $$$$') // Block math
        .replace(/\\\((.*?)\\\)/g, '$$ $1 $$'); // Inline math
};


function preprocessMathDelimiters(markdown) {
    // Replace \[ ... \] with $$ ... $$
    markdown = markdown.replace(/\\\[(.*?)\\\]/gs, (_, expr) => `$$${expr}$$`);
    // Replace \( ... \) with $ ... $
    markdown = markdown.replace(/\\\((.*?)\\\)/gs, (_, expr) => `$${expr}$`);
    return markdown;
}

function normaliseTeX(src) {
    return src
        // display:  \[ … \]  →  $$ … $$
        .replace(/\\\[((?:.|\n)+?)\\\]/g, (_, body) => `$$\n${body}\n$$`)
        // inline:   \( … \)  →  $ … $
        .replace(/\\\((.+?)\\\)/g,  (_, body) => `$${body}$`);
}


const undoPreprocess = s =>
    s.replace(/\$\$\$\$\s?(.*?)\s?\$\$\$\$/gs,'\$$ \$1\ $$')
        .replace(/\$\$\s?(.*?)\s?\$\$/g,'\$ \$1\ $')
        .replace(/\\\$/g,'$');

const p = React.memo(({ children }) => {
    return <p className="whitespace-pre-wrap">{children}</p>;
});


const FullMarkdown = ({ content }) => {
    const { theme } = useContext(ThemeContext);
    const { state, dispatch } = useContext(AppContext);

    // console.log( 'content', content);

    // const renderers = {
    //     listItem: ({ children }) => <li style={{ marginBottom: 0 }}>{children}</li>,
    // };

    const Pre = ({ children }) => {
        return <pre className="blog-pre">{children}</pre>;
    };

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
            children={normaliseTeX(content)}
            remarkPlugins={[supersub, remarkGfm, [remarkMath, { singleDollarTextMath: false }]]}
            // rehypePlugins={[[rehypeKatex, { output: 'mathml' }],
            rehypePlugins={[[rehypeKatex, { output: 'mathml' }],
                [
                    rehypeHighlight,
                    {
                        detect: true,
                        ignoreMissing: true,
                        // subset: langSubset,
                    },
                ],
                [rehypeRaw]]}
            components={{
                p,
                code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    let rawCode = extractCode(children);
                    return !inline && match ? (<div className={styles["code-block"]}>
                            <div onClick={() => handleCopyContent(rawCode)}
                                 className={styles["code-icons"]}
                                 title={"copy to clipboard"}>
                                <div className={`${styles["copy-paste"]} fa-icon -smaller`}>
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
// </div>
    );
};

export default FullMarkdown;
