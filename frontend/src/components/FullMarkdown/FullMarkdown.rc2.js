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
import rehypeReact from "rehype-react";
import {ThemeContext} from "../../redux/ThemeContext";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { twilight, vs, oneLight, oneDark, materialLight} from 'react-syntax-highlighter/dist/esm/styles/prism';

const preprocessContent = (content) => {
    content = content.replace(/\\\[/g, '$$').replace(/\\\]/g, '$$');
    content = content.replace(/\\\(/g, '$').replace(/\\\)/g, '$');
    return content;
};

const FullMarkdown = ({ content }) => {
    const { theme } = useContext(ThemeContext);

    // console.log( 'content', content);

    // const renderers = {
    //     listItem: ({ children }) => <li style={{ marginBottom: 0 }}>{children}</li>,
    // };

    const Pre = ({ children }) => {
        return <pre className="blog-pre">{children}</pre>;
    };
    return (
        <ReactMarkdown
            children={preprocessContent(content)}
            remarkPlugins={[supersub, remarkGfm, [remarkMath, { singleDollarTextMath: true }]]}
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
                // pre: Pre,
                // code({ node, inline, className = "blog-code", children, ...props }) {
                //     const match = /language-(\w+)/.exec(className || "");
                //     console.log('match', match);
                //     return !inline && match ? (
                //         <SyntaxHighlighter
                //             style={theme === 'dark' ? twilight : vs}
                //             language={match[1]}
                //             PreTag="div"
                //             {...props}
                //         >
                //             {String(children).replace(/\n$/, '')}
                //         </SyntaxHighlighter>
                //     ) : (
                //         <code className={className} {...props}>
                //             {String(children)}
                //         </code>
                //     );
                // }

                code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');

                    console.log( 'children', children);
                    return !inline && match ? (<div>
                        <SyntaxHighlighter style={twilight} PreTag="div" language={match[1]} {...props}>
                            {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter></div>
                    ) : (<code className={className} {...props}>
                            {children}
                        </code>
                    );
                },
            }}
        />
    );
};

export default FullMarkdown;
