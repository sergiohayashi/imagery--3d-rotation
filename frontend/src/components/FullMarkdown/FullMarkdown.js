import React, {useContext} from 'react';
import FullMarkdownWithMath from "./FullMarkdownWithMath";
import FullMarkdownNoMath from "./FullMarkdownNoMath";

const FullMarkdown = ({ content }) => {
    if (!content)
        return null;

    if (!content.includes('$') || content.includes('$$')) {
        return <FullMarkdownWithMath content={content}/>
    } else {
        return <FullMarkdownNoMath content={content}/>
    }
};

export default FullMarkdown;
