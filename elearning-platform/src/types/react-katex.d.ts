declare module "react-katex" {
    import { ComponentType } from "react";

    interface KatexProps {
        children?: string;
        math?: string;
        errorColor?: string;
        renderError?: (error: Error) => React.ReactNode;
    }

    export const BlockMath: ComponentType<KatexProps>;
    export const InlineMath: ComponentType<KatexProps>;
}
