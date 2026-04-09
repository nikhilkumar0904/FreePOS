/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    setup(vals){
        super.setup(vals);
        this.is_proforma = vals.is_proforma || false;
        this.is_training = vals.is_training || false;
        this.is_advance = vals.is_advance || false; 
        this.locked_for_processing = vals.locked_for_processing || false;

    },

    setIsProforma(v){
        this.is_proforma = !!v;
    },

    isProforma(){
        return !!this.is_proforma;
    },

    setIsTraining(v){
        this.is_training = !!v;
    },

    isTraining(){
        return !!this.is_training;
    },

    setIsAdvance(v){
        this.is_advance = !!v;
    },
    
    isAdvance(){
        return !!this.is_advance;
    },

    setProcessingLock(lock){
        this.locked_for_processing = !!lock;
    },

    isProcessingLocked(){
        return !!this.locked_for_processing;
    },

});
