
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Product, ProductVariation, ProductInventory, ProductEvent
from urllib.parse import unquote

def register_variant_routes(bp):
    
    @bp.route('/<int:product_id>/variants/new', methods=['POST'])
    @login_required
    def add_variant(product_id):
        """Quick add new product variant via AJAX"""
        from flask import jsonify
        
        if request.is_json:
            data = request.get_json()
            product_id = data.get('product_id')
            variant_name = data.get('name')
            sku = data.get('sku')
            description = data.get('description')

            product = Product.query.get_or_404(product_id)

            # Check if variant already exists
            if ProductVariation.query.filter_by(product_id=product_id, name=variant_name).first():
                return jsonify({'error': 'Variant already exists'}), 400

            variant = ProductVariation(
                product_id=product_id,
                name=variant_name,
                sku=sku,
                description=description
            )
            db.session.add(variant)
            db.session.commit()

            return jsonify({
                'success': True,
                'variant': {
                    'id': variant.id,
                    'name': variant.name,
                    'sku': variant.sku
                }
            })

        return jsonify({'error': 'Invalid request'}), 400

    @bp.route('/<int:product_id>/variant/<int:variation_id>')
    @login_required
    def view_variant(product_id, variation_id):
        """View individual product variation details"""
        from utils.unit_utils import get_global_unit_list
        from models import InventoryItem

        product = Product.query.get_or_404(product_id)
        variation = ProductVariation.query.get_or_404(variation_id)

        # Ensure variation belongs to this product
        if variation.product_id != product_id:
            flash('Variation not found for this product', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        # Get inventory for this specific variation
        inventory_entries = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variation.name
        ).order_by(ProductInventory.timestamp.asc()).all()

        # Group by size_label and unit
        size_groups = {}
        for entry in inventory_entries:
            if entry.quantity > 0:  # Only show active inventory
                key = f"{entry.size_label}_{entry.unit}"
                if key not in size_groups:
                    size_groups[key] = {
                        'size_label': entry.size_label,
                        'unit': entry.unit,
                        'total_quantity': 0,
                        'batches': []
                    }
                size_groups[key]['total_quantity'] += entry.quantity
                size_groups[key]['batches'].append(entry)

        # Get recent activity for this variation
        recent_events = ProductEvent.query.filter(
            ProductEvent.product_id == product_id,
            ProductEvent.note.like(f'%{variation.name}%')
        ).order_by(ProductEvent.timestamp.desc()).limit(20).all()

        # Get available containers for manual stock addition
        available_containers = InventoryItem.query.filter_by(
            type='container',
            is_archived=False
        ).filter(InventoryItem.quantity > 0).all()

        return render_template('products/view_variation.html',
                             product=product,
                             variation=variation,
                             size_groups=size_groups,
                             recent_events=recent_events,
                             available_containers=available_containers,
                             get_global_unit_list=get_global_unit_list)

    @bp.route('/<int:product_id>/variant/<int:variation_id>/edit', methods=['POST'])
    @login_required
    def edit_variant(product_id, variation_id):
        """Edit product variation details"""
        product = Product.query.get_or_404(product_id)
        variation = ProductVariation.query.get_or_404(variation_id)

        # Ensure variation belongs to this product
        if variation.product_id != product_id:
            flash('Variation not found for this product', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        name = request.form.get('name')
        description = request.form.get('description')

        if not name:
            flash('Variation name is required', 'error')
            return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))

        # Check if another variation has this name for the same product
        existing = ProductVariation.query.filter(
            ProductVariation.name == name,
            ProductVariation.product_id == product_id,
            ProductVariation.id != variation_id
        ).first()
        if existing:
            flash('Another variation with this name already exists for this product', 'error')
            return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))

        variation.name = name
        variation.description = description if description else None

        db.session.commit()
        flash('Variation updated successfully', 'success')
        return redirect(url_for('products.view_variant', product_id=product_id, variation_id=variation_id))

    @bp.route('/<int:product_id>/sku/<variant>/<size_label>')
    @login_required  
    def view_sku(product_id, variant, size_label):
        """View detailed SKU-level inventory with FIFO tracking"""
        from models import ProductInventory, ProductInventoryHistory
        from utils.fifo_generator import get_change_type_prefix, int_to_base36
        from datetime import datetime

        product = Product.query.get_or_404(product_id)

        # Get filter parameters
        change_type = request.args.get('change_type')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        sort_by = request.args.get('sort_by', 'timestamp_desc')
        active_only = request.args.get('active_only') == 'on'

        # Get all inventory entries for this SKU combination
        fifo_entries = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant,
            size_label=size_label
        ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

        # Get transaction history for this SKU
        history_query = ProductInventoryHistory.query.join(
            ProductInventory, ProductInventoryHistory.product_inventory_id == ProductInventory.id
        ).filter(
            ProductInventory.product_id == product_id,
            ProductInventory.variant == variant,
            ProductInventory.size_label == size_label
        )

        # Apply filters
        if change_type:
            history_query = history_query.filter(ProductInventoryHistory.change_type == change_type)

        if date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d')
                history_query = history_query.filter(ProductInventoryHistory.timestamp >= from_date)
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d')
                history_query = history_query.filter(ProductInventoryHistory.timestamp <= to_date)
            except ValueError:
                pass

        if active_only:
            history_query = history_query.filter(ProductInventoryHistory.remaining_quantity > 0)

        # Apply sorting
        if sort_by == 'timestamp_asc':
            history_query = history_query.order_by(ProductInventoryHistory.timestamp.asc())
        elif sort_by == 'quantity_desc':
            history_query = history_query.order_by(ProductInventoryHistory.quantity_change.desc())
        elif sort_by == 'quantity_asc':
            history_query = history_query.order_by(ProductInventoryHistory.quantity_change.asc())
        else:  # timestamp_desc (default)
            history_query = history_query.order_by(ProductInventoryHistory.timestamp.desc())

        history = history_query.all()

        # Calculate totals
        total_quantity = sum(entry.quantity for entry in fifo_entries)
        total_batches = len(set(entry.batch_id for entry in fifo_entries if entry.batch_id))

        # Get the variation object if it exists
        variation = ProductVariation.query.filter_by(
            product_id=product_id,
            name=variant
        ).first()

        return render_template('products/view_sku.html',
                             product=product,
                             variant=variant,
                             size_label=size_label,
                             variation=variation,
                             fifo_entries=fifo_entries,
                             history=history,
                             total_quantity=total_quantity,
                             total_batches=total_batches,
                             moment=datetime,
                             now=datetime.utcnow(),
                             get_change_type_prefix=get_change_type_prefix,
                             int_to_base36=int_to_base36)

    @bp.route('/<int:product_id>/sku/<variant>/<size_label>/edit', methods=['POST'])
    @login_required
    def edit_sku(product_id, variant, size_label):
        """Edit SKU for a specific product variant and size"""
        product = Product.query.get_or_404(product_id)
        variant = unquote(variant)
        size_label = unquote(size_label)

        sku = request.form.get('sku', '').strip()

        # Update all ProductInventory entries for this variant/size combination
        inventory_entries = ProductInventory.query.filter_by(
            product_id=product_id,
            variant=variant,
            size_label=size_label
        ).all()

        if not inventory_entries:
            flash('No inventory entries found for this variant/size combination', 'error')
            return redirect(url_for('products.view_sku', 
                                   product_id=product_id, variant=variant, size_label=size_label))

        # Check if SKU already exists for another product/variant/size combination
        if sku:
            existing_sku = ProductInventory.query.filter(
                ProductInventory.sku == sku,
                db.or_(
                    ProductInventory.product_id != product_id,
                    ProductInventory.variant != variant,
                    ProductInventory.size_label != size_label
                )
            ).first()

            if existing_sku:
                flash(f'SKU "{sku}" is already in use for another product/variant/size', 'error')
                return redirect(url_for('products.view_sku', 
                                       product_id=product_id, variant=variant, size_label=size_label))

        # Update all entries
        for entry in inventory_entries:
            entry.sku = sku if sku else None

        db.session.commit()

        if sku:
            flash(f'SKU updated to "{sku}" for {variant} - {size_label}', 'success')
        else:
            flash(f'SKU removed for {variant} - {size_label}', 'success')

        return redirect(url_for('products.view_sku', 
                               product_id=product_id, variant=variant, size_label=size_label))
