// src/FullMarkdown.jsx
import React, { useContext, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';             // <- optional, see comment above
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { twilight, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FaCopy } from 'react-icons/fa6';

import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github.css';

import styles from './FullMarkdown.module.css';
import { ThemeContext } from '../../redux/ThemeContext';
import { AppContext } from '../../redux/AppContext';
import { setInfoMessage, setErrorMessage } from '../../redux/actions';


/* ----------------  small helpers  ---------------- */
const Paragraph = memo(({ children }) => (
    <p className="whitespace-pre-wrap">{children}</p>
));

const getRawCode = children =>
    Array.isArray(children)
        ? children.map(getRawCode).join('')
        : typeof children === 'object'
            ? getRawCode(children.props?.children)
            : children;

const copyToClipboard = (dispatch, txt) => {
    if (!navigator.clipboard) {
        dispatch(setErrorMessage('Clipboard API not supported'));
        return;
    }
    navigator.clipboard
        .writeText(txt)
        .then(() => dispatch(setInfoMessage('Content copied to clipboard')))
        .catch(()   => dispatch(setErrorMessage('Could not copy text')));
};


/* ----------------  main component  ---------------- */
const FullMarkdown = ({ content = '' }) => {
    const { theme }           = useContext(ThemeContext);
    const { dispatch }        = useContext(AppContext);

    return (
        <ReactMarkdown
            remarkPlugins={[
                remarkGfm,
                // keep $..$ for normal text; users can still write $  ...  $ or $$ ... $$
                [remarkMath, { singleDollarTextMath: false }],
            ]}
            rehypePlugins={[
                // order matters: raw -> katex -> highlight
                // put rehypeRaw first only if you REALLY need raw HTML
                rehypeRaw,
                rehypeKatex,
                [rehypeHighlight, { detect: true, ignoreMissing: true }],
            ]}
            components={{
                p: Paragraph,

                code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    if (inline || !match) {
                        return (
                            <code className={className} {...props}>
                                {children}
                            </code>
                        );
                    }

                    const raw = getRawCode(children);

                    return (
                        <div className={styles['code-block']}>
                            <div
                                className={styles['code-icons']}
                                onClick={() => copyToClipboard(dispatch, raw)}
                                title="Copy to clipboard"
                            >
                                <div className={`${styles["copy-paste"]} fa-icon -smaller`}>
                                    <FaCopy/>
                                </div>
                            </div>
                            <div className={styles["code-part"]}>
                                <SyntaxHighlighter
                                    style={theme === 'dark' ? twilight : vs}
                                    language={match[1]}
                                    PreTag="div"
                                    {...props}
                                >
                                    {raw.replace(/\n$/, '')}
                                </SyntaxHighlighter>
                            </div>
                        </div>
                    );
                },
            }}
        >
            {content}
        </ReactMarkdown>
    );
};

export default FullMarkdown;
