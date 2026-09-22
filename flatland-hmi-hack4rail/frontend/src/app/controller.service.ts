import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { firstValueFrom, Subject } from 'rxjs'

const BACKEND_URL = 'http://localhost:5001'

export interface State {
  steps: number
  done: {
    __all__: boolean
    [key: string]: boolean
  }
}

@Injectable({
  providedIn: 'root',
})
export class ControllerService {
  private resetEvent = new Subject<void>()

  constructor(private http: HttpClient) {
    // Removed auto-reset on load — simulation is controlled from SystemX
  }

  public stepEnv(policyIndex: number = 0) {
    // Tell Flask brain to start running (simulation is continuous)
    return firstValueFrom(
      this.http.post<any>(`${BACKEND_URL}/control`, { command: 'start' })
    ).then(() => 0)
  }

  public resetEnv() {
    // Reset via Flask brain's control endpoint
    return firstValueFrom(
      this.http.post<any>(`${BACKEND_URL}/control`, { command: 'reset' })
    ).then((state) => {
      this.resetEvent.next()
      return state as State
    })
  }

  public observeReset() {
    return this.resetEvent.asObservable()
  }
}
