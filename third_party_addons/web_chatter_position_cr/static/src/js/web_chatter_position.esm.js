/** @odoo-module **/
import { FormCompiler } from "@web/views/form/form_compiler";
import { patch } from "@web/core/utils/patch";

patch(FormCompiler.prototype, {
    compileForm(el, params) {
        const res = super.compileForm(el, params);
        const chatterContainer = res.querySelector(".o-mail-Form-chatter");
        const chatterPosition = odoo.web_chatter_position || "bottom";

        if (chatterPosition === "sided") {
            const classes = res.getAttribute("t-attf-class");
            const newClasses = classes.replace('{{ __comp__.uiService.size < 6 ? "flex-column" : "flex-nowrap h-100" }}', 'flex-nowrap h-100');
            res.setAttribute("t-attf-class", `${newClasses}`);

            if (chatterContainer) {
                chatterContainer.classList.add('customSide');
            }

            return res;
        } else if (chatterPosition === "bottom") {
            const classes = res.getAttribute("t-attf-class");
            const formView = res.getElementsByClassName('o_form_sheet_bg')[0];
            $(formView).addClass('customBottom');
            $($(formView).parent()).find('.o-mail-Form-chatter').addClass('customBottom');
            const newClasses = classes.replace('{{ __comp__.uiService.size < 6 ? "flex-column" : "flex-nowrap h-100" }}', 'flex-column');
            res.setAttribute("t-attf-class", `${newClasses}`);
            return res;
        }

        return res;
    },

    compile(node, params) {
        const res = super.compile(node, params);
        const chatterPosition = odoo.web_chatter_position || "bottom";

        const chatterContainerHookXml = res.querySelector(".o-mail-Form-chatter");
        if (!chatterContainerHookXml) {
            return res; // no chatter, keep the result as it is
        }

        if (chatterPosition === "sided") {
            const classes = chatterContainerHookXml.getAttribute("t-attf-class");
            if (classes) {
                const newClasses = classes.replace('{{ __comp__.uiService.size >= 6 ? "o-aside" : "mt-4 mt-md-0" }}', 'o-aside');
                chatterContainerHookXml.setAttribute("t-attf-class", `${newClasses}`);
            }
            return res;
        } else if (chatterPosition === "bottom") {
            const classes = chatterContainerHookXml.getAttribute("t-attf-class");
            if (classes) {
                const newClasses = classes.replace('{{ __comp__.uiService.size >= 6 ? "o-aside" : "mt-4 mt-md-0" }}', 'mt- mt-md-0');
                chatterContainerHookXml.setAttribute("t-attf-class", `${newClasses}`);
            }
            return res;
        }
        return res;
    },
});
