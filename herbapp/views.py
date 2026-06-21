from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, DetailView
from django.http import JsonResponse
from django.db.models import Q

from .models import HerbBatch, ProcessingRound, Acceptance
from .forms import HerbBatchForm, ProcessingRoundForm, AcceptanceForm


class BatchListView(ListView):
    model = HerbBatch
    template_name = 'herbapp/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        if keyword:
            queryset = queryset.filter(
                Q(batch_no__icontains=keyword) | Q(herb_name__icontains=keyword)
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', '')
        ctx['status_choices'] = HerbBatch.STATUS_CHOICES
        return ctx


class BatchCreateView(CreateView):
    model = HerbBatch
    form_class = HerbBatchForm
    template_name = 'herbapp/batch_form.html'
    success_url = reverse_lazy('herbapp:batch_list')


class BatchDetailView(DetailView):
    model = HerbBatch
    template_name = 'herbapp/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rounds = self.object.rounds.all().order_by('round_no')
        ctx['rounds'] = rounds
        ctx['next_round_no'] = self.object.get_next_round_no()
        ctx['can_add_round'] = self.object.can_add_round()
        ctx['can_accept'] = self.object.can_accept()
        ctx['has_accepted'] = self.object.status == HerbBatch.STATUS_ACCEPTED
        return ctx


class RoundCreateView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_add_round():
            return redirect('herbapp:batch_detail', pk=pk)
        form = ProcessingRoundForm(batch=batch)
        return render(request, 'herbapp/round_form.html', {
            'form': form,
            'batch': batch,
            'round_no': batch.get_next_round_no(),
        })

    def post(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_add_round():
            return redirect('herbapp:batch_detail', pk=pk)

        form = ProcessingRoundForm(request.POST, batch=batch)
        if form.is_valid():
            round_obj = form.save(commit=False)
            round_obj.batch = batch
            round_obj.round_no = batch.get_next_round_no()
            round_obj.save()
            batch.update_status()
            return redirect('herbapp:batch_detail', pk=pk)

        return render(request, 'herbapp/round_form.html', {
            'form': form,
            'batch': batch,
            'round_no': batch.get_next_round_no(),
        })


class AcceptanceView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_accept():
            return redirect('herbapp:batch_detail', pk=pk)
        form = AcceptanceForm()
        return render(request, 'herbapp/acceptance_form.html', {
            'form': form,
            'batch': batch,
        })

    def post(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_accept():
            return redirect('herbapp:batch_detail', pk=pk)

        form = AcceptanceForm(request.POST)
        if form.is_valid():
            acceptance = form.save(commit=False)
            acceptance.batch = batch
            acceptance.save()
            batch.status = HerbBatch.STATUS_ACCEPTED
            batch.save()
            return redirect('herbapp:batch_detail', pk=pk)

        return render(request, 'herbapp/acceptance_form.html', {
            'form': form,
            'batch': batch,
        })


class BatchChartView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        rounds = batch.rounds.all().order_by('round_no')

        labels = ['初始']
        weight_data = [float(batch.initial_weight)]
        color_map = {
            ProcessingRound.COLOR_EXCELLENT: 4,
            ProcessingRound.COLOR_GOOD: 3,
            ProcessingRound.COLOR_NORMAL: 2,
            ProcessingRound.COLOR_ABNORMAL: 1,
        }
        color_data = []

        for r in rounds:
            labels.append(f'第{r.round_no}轮')
            weight_data.append(float(r.weight))
            color_data.append({
                'round': r.round_no,
                'rating': r.get_color_rating_display(),
                'value': color_map.get(r.color_rating, 0),
                'abnormal': r.color_rating == ProcessingRound.COLOR_ABNORMAL,
            })

        return JsonResponse({
            'labels': labels,
            'weight_data': weight_data,
            'color_data': color_data,
            'initial_weight': float(batch.initial_weight),
            'required_rounds': batch.required_rounds,
        })
