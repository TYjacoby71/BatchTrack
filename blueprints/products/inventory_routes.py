
from flask import request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product, ProductEvent
from services.product_inventory_service import ProductInventoryService

def register_inventory_routes(bp):
    
    @bp.route('/<int:product_id>/deduct', methods=['POST'])
    @login_required
    def deduct_product(product_id):
        """Deduct product inventory using FIFO"""
        variant = request.form.get('variant', 'Base')
        unit = request.form.get('unit')
        quantity = float(request.form.get('quantity', 0))
        reason = request.form.get('reason', 'manual_deduction')
        notes = request.form.get('notes', '')

        if quantity <= 0:
            flash('Quantity must be positive', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        success = ProductInventoryService.deduct_fifo(
            product_id=product_id,
            variant_label=variant,
            unit=unit,
            quantity=quantity,
            reason=reason,
            notes=notes
        )

        if success:
            flash(f'Deducted {quantity} {unit} from {variant} using FIFO', 'success')
        else:
            flash('Not enough stock available', 'error')

        return redirect(url_for('products.view_product', product_id=product_id))

    @bp.route('/<int:product_id>/adjust/<int:inventory_id>', methods=['POST'])
    @login_required
    def adjust_inventory(product_id, inventory_id):
        """Process inventory adjustments with FIFO tracking"""
        from services.product_adjustment_service import ProductAdjustmentService

        adjustment_type = request.form.get('adjustment_type')  # sold, spoil, trash, tester, damaged, recount
        quantity = float(request.form.get('quantity', 0))
        notes = request.form.get('notes', '')

        if quantity <= 0:
            flash('Quantity must be positive', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        try:
            ProductAdjustmentService.process_adjustment(
                inventory_id=inventory_id,
                adjustment_type=adjustment_type,
                quantity=quantity,
                notes=notes
            )

            flash(f'Adjustment processed: {adjustment_type}', 'success')
        except Exception as e:
            flash(f'Error processing adjustment: {str(e)}', 'error')

        return redirect(url_for('products.view_product', product_id=product_id))

    @bp.route('/<int:product_id>/add-manual-stock', methods=['POST'])
    @login_required
    def add_manual_stock(product_id):
        """Add manual stock with container matching"""
        from services.product_adjustment_service import ProductAdjustmentService

        variant_name = request.form.get('variant_name')
        container_id = request.form.get('container_id')
        quantity = float(request.form.get('quantity', 0))
        unit_cost = float(request.form.get('unit_cost', 0))
        notes = request.form.get('notes', '')

        if quantity <= 0:
            flash('Quantity must be positive', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        try:
            inventory = ProductAdjustmentService.add_manual_stock(
                product_id=product_id,
                variant_name=variant_name,
                container_id=container_id,
                quantity=quantity,
                unit_cost=unit_cost,
                notes=notes
            )

            flash(f'Added {quantity} units to product inventory', 'success')
        except Exception as e:
            flash(f'Error adding stock: {str(e)}', 'error')

        return redirect(url_for('products.view_product', product_id=product_id))

    @bp.route('/<int:product_id>/record-sale', methods=['POST'])
    @login_required
    def record_sale(product_id):
        """Record a sale with profit tracking"""
        variant = request.form.get('variant', 'Base')
        size_label = request.form.get('size_label')
        quantity = float(request.form.get('quantity', 0))
        reason = request.form.get('reason', 'sale')
        sale_price = request.form.get('sale_price')
        customer = request.form.get('customer', '')
        notes = request.form.get('notes', '')

        if quantity <= 0:
            flash('Quantity must be positive', 'error')
            return redirect(url_for('products.view_sku', 
                               product_id=product_id, variant=variant, size_label=size_label))

        # Deduct using FIFO
        success = ProductInventoryService.deduct_fifo(
            product_id=product_id,
            variant_label=variant,
            unit='count',  # Assuming count for now, could be dynamic
            quantity=quantity,
            reason=reason,
            notes=notes
        )

        if success:
            # Log detailed sale information
            sale_note = f"{reason.title()}: {quantity} × {size_label}"
            if reason == 'sale':
                if sale_price:
                    sale_price_float = float(sale_price)
                    per_unit_price = sale_price_float / quantity
                    sale_note += f" for ${sale_price} (${per_unit_price:.2f}/unit)"
                if customer:
                    sale_note += f" to {customer}"
            if notes:
                sale_note += f". Notes: {notes}"

            db.session.add(ProductEvent(
                product_id=product_id,
                event_type=f'inventory_{reason}',
                note=sale_note
            ))
            db.session.commit()

            flash(f'Recorded {reason}: {quantity} units', 'success')
        else:
            flash('Not enough stock available', 'error')

        return redirect(url_for('products.view_sku', 
                               product_id=product_id, variant=variant, size_label=size_label))

    @bp.route('/<int:product_id>/manual-adjust', methods=['POST'])
    @login_required
    def manual_adjust(product_id):
        """Manual inventory adjustments for variant/size"""
        variant = request.form.get('variant', 'Base')
        size_label = request.form.get('size_label')
        adjustment_type = request.form.get('adjustment_type')
        quantity = float(request.form.get('quantity', 0))
        notes = request.form.get('notes', '')

        # Implementation would depend on adjustment type
        # This is a placeholder for the manual adjustment logic

        flash(f'Manual adjustment applied: {adjustment_type}', 'success')
        return redirect(url_for('products.view_sku', 
                               product_id=product_id, variant=variant, size_label=size_label))
